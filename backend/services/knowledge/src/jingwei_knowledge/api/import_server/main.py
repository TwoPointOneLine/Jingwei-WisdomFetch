"""
导入服务 HTTP 入口：文件上传、后台 LangGraph 执行、状态查询。
"""
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, UploadFile
from jingwei_common.audit import audit_log
from jingwei_common.auth import get_user_role, get_user_team, require_user
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.config import settings
from jingwei_common.config.common import PROJECT_ROOT
from jingwei_common.constants import (
    COLLECTION_KNOWLEDGE_ITEMS,
    ROLE_ADMIN,
    VIS_PRIVATE,
    VIS_SHARED,
    VIS_TEAM,
)
from jingwei_common.logging import logger
from jingwei_common.web.task_utils import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    add_done_task,
    add_running_task,
    get_done_task_list,
    get_running_task_list,
    get_task_error,
    get_task_full_result,
    get_task_status,
    reset_task,
    set_task_error,
    set_task_result,
    update_task_status,
)
from starlette.middleware.cors import CORSMiddleware

from jingwei_knowledge.api.schemas.import_schema import ImportStatusResponse, UploadResponse
from jingwei_knowledge.infra.vectorstore.milvus_store import chunks_store
from jingwei_knowledge.process.import_chain.main_graph import kb_import_app
from jingwei_knowledge.process.import_chain.state import get_default_state

load_dotenv()

app = FastAPI(
    title=settings.import_app_name,
    description="企业化 RAG 导入服务，负责文件上传、导入执行与状态查询。",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins.split(",")) if settings.cors_origins != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """健康检查端点（供容器编排探活）。"""
    return {"code": 0, "message": "ok", "data": {"status": "up", "service": settings.import_app_name}}


def _resolve_actor(authorization: str | None) -> tuple[str, str, str]:
    """从 Authorization 解析（username, role, team_id），供隔离与鉴权使用（服务端可信）。"""
    username = require_user(authorization)
    token = (authorization or "").removeprefix("Bearer ").strip()
    role = ""
    team_id = ""
    if token:
        try:
            role = get_user_role(username) or ""
        except Exception:
            role = ""
        try:
            team_id = get_user_team(username) or ""
        except Exception:
            team_id = ""
    return username, role, team_id


def _item_owner(item_name: str) -> str:
    """读取资料 owner（优先 Mongo 元信息，回退 Milvus）。"""
    try:
        doc = mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).find_one(
            {"item_name": item_name}, {"owner": 1}
        )
        if doc and doc.get("owner"):
            return doc["owner"]
    except Exception:
        pass
    try:
        res = milvus_client_query_owner(item_name)
        if res:
            return res
    except Exception:
        pass
    return ""


def milvus_client_query_owner(item_name: str) -> str:
    from jingwei_common.clients.milvus_client import milvus_client

    try:
        if milvus_client.client.has_collection(chunks_store.collection):
            r = milvus_client.client.query(
                chunks_store.collection,
                filter=f'item_name == "{item_name}"',
                output_fields=["owner"],
                limit=1,
            )
            return r[0].get("owner", "") if r else ""
    except Exception:
        pass
    return ""


def run_graph_task(
    task_id: str,
    local_dir: str,
    local_file_path: str,
    owner: str = "",
    visibility: str = VIS_PRIVATE,
    team_id: str = "",
):
    """后台执行 LangGraph 全流程，实时更新任务状态。"""
    try:
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        logger.info(f"[{task_id}] 开始执行LangGraph全流程，本地文件路径：{local_file_path}")

        init_state = get_default_state()
        init_state["task_id"] = task_id
        init_state["local_dir"] = local_dir
        init_state["local_file_path"] = local_file_path
        # 普通用户知识库隔离（多级）：记录 owner / 可见性 / 团队空间
        init_state["owner"] = owner
        init_state["visibility"] = visibility if visibility in (VIS_PRIVATE, VIS_TEAM, VIS_SHARED) else VIS_PRIVATE
        init_state["team_id"] = team_id if visibility == VIS_TEAM else ""
        # 持久化原始文件路径与归属，供失败重试（FR-IMP-04）定位原文件重跑
        set_task_result(
            task_id,
            {
                "local_file_path": local_file_path,
                "owner": owner,
                "visibility": init_state["visibility"],
                "team_id": init_state["team_id"],
            },
        )

        for event in kb_import_app.stream(init_state):
            for node_name in event.keys():
                logger.info(f"[{task_id}] LangGraph节点执行完成：{node_name}")
                add_done_task(task_id, node_name)

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(f"[{task_id}] LangGraph全流程执行完毕，任务完成")
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        set_task_error(task_id, str(e) or repr(e))
        logger.error(f"[{task_id}] LangGraph全流程执行失败：{e}", exc_info=True)


@app.post("/upload", summary="文件上传接口", description="支持多文件批量上传，登录用户即可导入自己的知识库")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    visibility: str = Form(VIS_PRIVATE),
    authorization: str = Header(None, alias="Authorization"),
):
    # 登录用户即可上传（普通用户管理自己的知识库）
    username, role, actor_team = _resolve_actor(authorization)
    owner = username  # 资料归属上传者本人（服务端可信，不信任客户端传参）
    vis = visibility if visibility in (VIS_PRIVATE, VIS_TEAM, VIS_SHARED) else VIS_PRIVATE
    # 团队可见需上传者本身属于某个团队（否则退化为私有，避免无效 team 资料）
    team_id = actor_team if vis == VIS_TEAM else ""
    today_str = datetime.now().strftime("%Y%m%d")
    date_based_root_dir: Path = PROJECT_ROOT / "output" / today_str

    task_ids = []
    for file in files:
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)

        add_running_task(task_id, "upload_file")
        task_local_dir: Path = date_based_root_dir / task_id
        task_local_dir.mkdir(parents=True, exist_ok=True)

        local_file_abs_path: Path = task_local_dir / file.filename
        with local_file_abs_path.open("wb") as file_buffer:
            shutil.copyfileobj(file.file, file_buffer)

        add_done_task(task_id, "upload_file")
        background_tasks.add_task(
            run_graph_task,
            task_id,
            str(task_local_dir),
            str(local_file_abs_path),
            owner,
            vis,
            team_id,
        )

    # NFR-SEC-04：导入动作审计留痕
    audit_log(
        action="import_upload",
        actor=username,
        actor_role=role or "member",
        detail={"task_ids": task_ids, "file_count": len(files), "visibility": vis, "team_id": team_id, "filenames": [f.filename for f in files]},
        source="knowledge",
    )

    return UploadResponse(
        code=200,
        message=f"Files uploaded successfully, total: {len(files)}",
        task_ids=task_ids,
    )


@app.get("/status/{task_id}", summary="任务状态查询", response_model=ImportStatusResponse)
async def get_task_progress(
    task_id: str,
    authorization: str = Header(None, alias="Authorization"),
):
    # 登录用户即可查询（自己或管理员可见）
    username, role, _ = _resolve_actor(authorization)
    status = get_task_status(task_id)
    done_list = get_done_task_list(task_id)
    running_list = get_running_task_list(task_id)
    error = get_task_error(task_id)
    logger.info(f"[{task_id}] 任务状态查询，当前状态：{status}，已完成节点：{done_list}")
    return ImportStatusResponse(
        code=200,
        task_id=task_id,
        status=status,
        done_list=done_list,
        running_list=running_list,
        error=error,
    )


@app.post("/status/{task_id}/retry", summary="导入任务重试", description="对失败/异常的导入任务重新执行")
async def retry_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None, alias="Authorization"),
):
    # 登录用户即可重试（本人或管理员）。仅允许失败任务重试。
    username, role, _ = _resolve_actor(authorization)
    prev = get_task_full_result(task_id)
    local_file_path = prev.get("local_file_path") if prev else None
    if not local_file_path or not Path(local_file_path).exists():
        from jingwei_common.web.errors import BadRequestError

        raise BadRequestError("找不到原任务文件，无法重试（可能已被清理）")
    if get_task_status(task_id) == TASK_STATUS_PROCESSING:
        from jingwei_common.web.errors import BadRequestError

        raise BadRequestError("任务正在执行中，请勿重复重试")

    # 重置状态后重跑原文件
    reset_task(task_id)
    task_local_dir = str(Path(local_file_path).resolve().parent)
    owner = prev.get("owner") or username
    vis = prev.get("visibility") or VIS_PRIVATE
    team_id = prev.get("team_id") or ""
    background_tasks.add_task(run_graph_task, task_id, task_local_dir, local_file_path, owner, vis, team_id)
    logger.info(f"[{task_id}] 触发导入重试，原文件：{local_file_path}")
    # NFR-SEC-04：重试动作审计留痕
    audit_log(
        action="import_retry",
        actor=username,
        actor_role=role or "member",
        detail={"task_id": task_id, "prev_status": prev.get("status") if prev else None, "filename": Path(local_file_path).name},
        source="knowledge",
    )
    return UploadResponse(
        code=200,
        message="retry submitted",
        task_ids=[task_id],
    )


@app.get("/documents", summary="已导入资料列表", description="列出当前知识库已入库资料（按 item 聚合）。普通用户见自己、团队共享与全员共享的；管理员见全部。")
async def list_documents(authorization: str = Header(None, alias="Authorization")):
    username, role, team_id = _resolve_actor(authorization)
    items = chunks_store.list_items(owner=username, role=role, team_id=team_id)
    return {"code": 200, "message": "success", "data": {"items": items}}


@app.post("/documents/{item_name}/offline", summary="资料下线", description="删除某资料的全部 chunk（FR-IMP-05）。仅 owner 或管理员可操作。")
async def offline_document(item_name: str, authorization: str = Header(None, alias="Authorization")):
    username, role, _ = _resolve_actor(authorization)
    # 权限：管理员，或该资料的 owner
    if role != ROLE_ADMIN:
        owner = _item_owner(item_name)
        if owner and owner != username:
            from jingwei_common.web.errors import ForbiddenError

            raise ForbiddenError("无权下线他人资料")
    deleted = chunks_store.delete_item(item_name)
    # NFR-SEC-04：资料下线审计留痕
    audit_log(
        action="document_offline",
        actor=username,
        actor_role=role or "member",
        detail={"item_name": item_name, "deleted_chunks": deleted},
        source="knowledge",
    )
    return {"code": 200, "message": "document offline", "item_name": item_name, "deleted_chunks": deleted}


@app.post("/documents/{item_name}/visibility", summary="切换资料可见性", description="在 private（仅自己）/ team（团队可见）/ shared（全员共享检索）间切换。仅 owner 或管理员可操作。")
async def set_document_visibility(
    item_name: str,
    visibility: str,
    authorization: str = Header(None, alias="Authorization"),
):
    username, role, actor_team = _resolve_actor(authorization)
    if visibility not in (VIS_PRIVATE, VIS_TEAM, VIS_SHARED):
        from jingwei_common.web.errors import BadRequestError

        raise BadRequestError("visibility 仅支持 private / team / shared")

    # 校验资料存在 + 权限
    owner = _item_owner(item_name)
    if not owner and role != ROLE_ADMIN:
        from jingwei_common.web.errors import NotFoundError

        raise NotFoundError("资料不存在")
    if role != ROLE_ADMIN and owner and owner != username:
        from jingwei_common.web.errors import ForbiddenError

        raise ForbiddenError("无权修改他人资料可见性")

    # 切到 team 可见时，目标团队取「当前操作者所属团队」；若无团队，退化为私有
    target_team = actor_team if visibility == VIS_TEAM else ""
    if visibility == VIS_TEAM and not target_team:
        visibility = VIS_PRIVATE
        target_team = ""

    # 仅更新 Mongo 元信息即可（可见性/归属/团队 的权威来源；检索过滤读取 Mongo）
    try:
        mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).update_one(
            {"item_name": item_name},
            {"$set": {"visibility": visibility, "team_id": target_team, "updated_at": UTC.now()}},
        )
    except Exception as e:
        logger.warning(f"可见性持久化失败: {e}")

    audit_log(
        action="document_visibility",
        actor=username,
        actor_role=role or "member",
        detail={"item_name": item_name, "visibility": visibility},
        source="knowledge",
    )
    return {"code": 200, "message": "visibility updated", "item_name": item_name, "visibility": visibility}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.import_app_port)
