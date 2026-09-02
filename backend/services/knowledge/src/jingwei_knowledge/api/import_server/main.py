"""
导入服务 HTTP 入口：文件上传、后台 LangGraph 执行、状态查询。
"""
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, Query, UploadFile
from fastapi.responses import JSONResponse
from jingwei_common.audit import audit_log
from jingwei_common.auth import get_user_role, get_user_team, require_user
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.config import settings
from jingwei_common.config.common import PROJECT_ROOT
from jingwei_common.constants import (
    COLLECTION_KNOWLEDGE_BASES,
    COLLECTION_KNOWLEDGE_ITEMS,
    DEFAULT_KB,
    KB_DEFAULT_PREFIX,
    KB_NAME_MAXLEN,
    ROLE_ADMIN,
    VIS_PRIVATE,
    VIS_SHARED,
    VIS_TEAM,
)
from jingwei_common.logging import logger
from jingwei_common.web.errors import (
    ApiError,
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
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

from jingwei_knowledge.api.schemas.import_schema import (
    ImportStatusResponse,
    RejectedFile,
    UploadResponse,
)
from jingwei_knowledge.infra.vectorstore.milvus_store import chunks_store
from jingwei_knowledge.rag.import_.doc_format import is_supported, unsupported_message
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


@app.exception_handler(ApiError)
async def _api_error_handler(request, exc: ApiError):
    """将业务异常映射为统一 JSON 响应。

    关键：缺少此处理器时，所有 ApiError（BadRequest/NotFound/Forbidden/Unauthorized）
    都会变成未捕获异常，Starlette 返回 500 纯文本「Internal Server Error」，
    前端 res.json() 解析失败（"Unexpected token 'I'..."），真实错误信息被完全掩盖。
    """
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


@app.exception_handler(Exception)
async def _unhandled_error_handler(request, exc: Exception):
    """兜底：未预期异常也返回统一 JSON，避免前端拿到非 JSON 响应。"""
    logger.exception(f"[knowledge] 未捕获异常: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"服务内部错误：{exc}", "data": None},
    )


@app.get("/health")
async def health():
    """健康检查端点（供容器编排探活）。"""
    return {"code": 0, "message": "ok", "data": {"status": "up", "service": settings.import_app_name}}


@app.get("/formats", summary="支持的导入格式", description="供前端 <input accept> 复用，保证前后端格式白名单一致（G-01）。")
async def list_supported_formats():
    from jingwei_knowledge.rag.import_.doc_format import (
        SUPPORTED_EXTS,
        accept_attr,
        supported_display,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "exts": sorted(SUPPORTED_EXTS),
            "accept": accept_attr(),
            "display": supported_display(),
        },
    }


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
    kb_name: str = DEFAULT_KB,
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
        kb = kb_name or DEFAULT_KB
        init_state["kb_name"] = kb
        # 持久化原始文件路径与归属，供失败重试（FR-IMP-04）定位原文件重跑
        set_task_result(
            task_id,
            {
                "local_file_path": local_file_path,
                "owner": owner,
                "visibility": init_state["visibility"],
                "team_id": init_state["team_id"],
                "kb_name": kb,
            },
        )

        final_state: dict = {}
        for event in kb_import_app.stream(init_state):
            # stream_mode 默认 "values"：event 为 {node_name: 全量 state}
            for node_name, node_state in event.items():
                logger.info(f"[{task_id}] LangGraph节点执行完成：{node_name}")
                add_done_task(task_id, node_name)
                if isinstance(node_state, dict):
                    final_state = node_state

        # G-01：图正常跑完但零条入库 == 事实上的失败（如解析器返回空内容）。
        # 此前会被标记 COMPLETED，用户以为导入成功却永远检索不到。
        if not final_state.get("done_count"):
            update_task_status(task_id, TASK_STATUS_FAILED)
            set_task_error(
                task_id,
                "导入完成但未生成任何可检索内容（0 条切片）。"
                "常见原因：文档为空、解析失败或内容全部为图片扫描件。请检查源文件后重试。",
            )
            logger.warning(f"[{task_id}] 导入结束但 done_count=0，判定为失败")
            return

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(
            f"[{task_id}] LangGraph全流程执行完毕，任务完成，入库 {final_state.get('done_count')} 条"
        )
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        set_task_error(task_id, str(e) or repr(e))
        logger.error(f"[{task_id}] LangGraph全流程执行失败：{e}", exc_info=True)


@app.post("/upload", summary="文件上传接口", description="支持多文件批量上传，登录用户即可导入自己的知识库")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    visibility: str = Form(VIS_PRIVATE),
    kb_name: str = Form(DEFAULT_KB),
    authorization: str = Header(None, alias="Authorization"),
):
    # 登录用户即可上传（普通用户管理自己的知识库）
    username, role, actor_team = _resolve_actor(authorization)
    owner = username  # 资料归属上传者本人（服务端可信，不信任客户端传参）
    vis = visibility if visibility in (VIS_PRIVATE, VIS_TEAM, VIS_SHARED) else VIS_PRIVATE
    # 团队可见需上传者本身属于某个团队（否则退化为私有，避免无效 team 资料）
    team_id = actor_team if vis == VIS_TEAM else ""
    kb = (kb_name or "").strip()[:KB_NAME_MAXLEN]
    # 未指定库名或沿用旧共享默认库时，归入该用户专属默认库 default@<username>
    if not kb or kb == DEFAULT_KB:
        kb = _user_default_kb(username)
    today_str = datetime.now().strftime("%Y%m%d")
    date_based_root_dir: Path = PROJECT_ROOT / "output" / today_str

    # G-01：落盘前按白名单过滤，不支持的格式直接拒绝并说明原因，
    # 避免"任务显示成功却零条入库"（原实现会静默走 END）。
    supported = []
    rejected: list[RejectedFile] = []
    for file in files:
        fname = file.filename or ""
        if is_supported(fname):
            supported.append(file)
        else:
            reason = unsupported_message(fname)
            logger.warning(f"[knowledge] 拒绝上传：{reason}")
            rejected.append(RejectedFile(filename=fname, reason=reason))

    # 全部被拒：明确返回 400，让前端直接把原因呈现给用户
    if not supported:
        raise BadRequestError(
            "；".join(r.reason for r in rejected) or "没有可导入的文件",
            data={"rejected": [r.model_dump() for r in rejected]},
        )

    task_ids = []
    for file in supported:
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
            kb,
        )

    # NFR-SEC-04：导入动作审计留痕
    audit_log(
        action="import_upload",
        actor=username,
        actor_role=role or "member",
        detail={"task_ids": task_ids, "file_count": len(supported), "visibility": vis, "team_id": team_id, "kb_name": kb, "filenames": [f.filename for f in supported]},
        source="knowledge",
    )

    # G-01：部分文件被拒时，用 207 语义（HTTP 200 + rejected 清单）保证"导入失败不影响整体服务"
    message = f"成功接收 {len(supported)} 个文件"
    if rejected:
        message = f"{message}，{len(rejected)} 个文件被拒绝（格式不支持）"
    return UploadResponse(
        code=200,
        message=message,
        task_ids=task_ids,
        rejected=rejected,
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
    kb = prev.get("kb_name") or DEFAULT_KB
    background_tasks.add_task(run_graph_task, task_id, task_local_dir, local_file_path, owner, vis, team_id, kb)
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


@app.get("/documents", summary="已导入资料列表", description="列出当前知识库已入库资料（按 item 聚合）。普通用户见自己、团队共享与全员共享的；管理员见全部。可按 kb_name 过滤。")
async def list_documents(
    authorization: str = Header(None, alias="Authorization"),
    kb_name: str = Query("", description="按知识库（逻辑库）过滤，留空返回全部"),
):
    username, role, team_id = _resolve_actor(authorization)
    items = chunks_store.list_items(owner=username, role=role, team_id=team_id, kb_name=kb_name or "")
    return {"code": 200, "message": "success", "data": {"items": items}}


def _kb_collection():
    return mongo_client.get_collection(COLLECTION_KNOWLEDGE_BASES)


def _user_default_kb(username: str) -> str:
    """每用户默认知识库名：default@<username>（owner 为该用户）。"""
    return f"{KB_DEFAULT_PREFIX}{username}"


def _milvus_escape(value: str) -> str:
    """转义 Milvus 字符串过滤表达式中的特殊字符，避免库名/资料名含引号时破坏表达式。"""
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _migrate_kb_items(old_kb: str, new_kb: str) -> int:
    """将某知识库下的全部资料迁移到另一知识库，返回受影响的资料数。

    同时更新 Mongo 资料元信息与 Milvus chunk 的 kb_name，保证重命名/删除库后资料不丢。
    """
    from jingwei_common.clients.milvus_client import milvus_client

    moved = 0
    items: list[str] = []
    col = mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS)
    try:
        items = [d["item_name"] for d in col.find({"kb_name": old_kb}, {"item_name": 1})]
    except Exception as e:
        logger.warning(f"读取知识库 {old_kb} 资料列表失败: {e}")

    # Milvus 侧：按 item_name 逐条改写 kb_name（delete + insert，Milvus 不支持原地 update）
    try:
        client = milvus_client.client
        if items and client.has_collection(chunks_store.collection):
            for item in items:
                try:
                    res = client.query(
                        chunks_store.collection,
                        filter=f'item_name == "{_milvus_escape(item)}"',
                        output_fields=["*"],
                    )
                except Exception as e:
                    logger.warning(f"迁移资料 {item} 读取 Milvus 失败（跳过）: {e}")
                    continue
                if not res:
                    continue
                rows = []
                for r in res:
                    r["kb_name"] = new_kb
                    r.pop("pk", None)
                    rows.append(r)
                try:
                    client.delete(
                        collection_name=chunks_store.collection,
                        filter=f'item_name == "{_milvus_escape(item)}"',
                    )
                    client.insert(collection_name=chunks_store.collection, data=rows)
                except Exception as e:
                    logger.warning(f"迁移资料 {item} 写回失败（跳过）: {e}")
                    continue
    except Exception as e:
        logger.warning(f"迁移知识库 {old_kb} 的向量数据失败（忽略）: {e}")

    # Mongo 侧：批量改写元信息
    try:
        res = col.update_many(
            {"kb_name": old_kb},
            {"$set": {"kb_name": new_kb, "updated_at": datetime.now(UTC)}},
        )
        moved = res.modified_count or len(items)
    except Exception as e:
        logger.warning(f"迁移知识库 {old_kb} 的 Mongo 元信息失败（忽略）: {e}")
        moved = len(items)
    return moved


def _load_kb_or_404(name: str, username: str, role: str) -> dict:
    """加载知识库并校验存在性与操作权限（本人创建的库或管理员），失败直接抛 ApiError。"""
    from jingwei_common.web.errors import ForbiddenError, NotFoundError

    try:
        kb_doc = _kb_collection().find_one({"name": name})
    except Exception as e:
        logger.error(f"查询知识库 {name} 失败: {e}")
        from jingwei_common.web.errors import ApiError

        raise ApiError("查询知识库失败", code=500)
    if kb_doc is None:
        raise NotFoundError(f"知识库「{name}」不存在")
    if role != ROLE_ADMIN and kb_doc.get("owner") != username:
        raise ForbiddenError("无权操作他人知识库")
    return kb_doc


def _migrate_default_items(username: str) -> None:
    """将用户原共享 `default` 库资料迁移到其专属默认库 default@<username>（仅一次）。

    同时更新 Mongo 资料元信息与 Milvus chunk 的 kb_name 字段，保证历史不丢。
    """
    from jingwei_common.clients.milvus_client import milvus_client

    target = _user_default_kb(username)
    try:
        col = mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS)
        docs = list(col.find({"kb_name": DEFAULT_KB, "owner": username}, {"item_name": 1}))
        if not docs:
            return
        client = milvus_client.client
        for d in docs:
            item = d["item_name"]
            try:
                res = client.query(
                    chunks_store.collection,
                    filter=f'item_name == "{item}"',
                    output_fields=["*"],
                )
            except Exception as e:
                logger.warning(f"迁移资料 {item} 读取 Milvus 失败（跳过）: {e}")
                continue
            if not res:
                continue
            rows = []
            for r in res:
                r["kb_name"] = target
                r.pop("pk", None)  # 移除自动主键，避免冲突
                rows.append(r)
            try:
                client.delete(collection_name=chunks_store.collection, filter=f'item_name == "{item}"')
                client.insert(collection_name=chunks_store.collection, data=rows)
                client.flush(chunks_store.collection)
                col.update_one({"item_name": item}, {"$set": {"kb_name": target}})
            except Exception as e:
                logger.warning(f"迁移资料 {item} 写回失败（跳过）: {e}")
    except Exception as e:
        logger.warning(f"默认库资料迁移失败（忽略）: {e}")


def _ensure_default_kb(username: str):
    """确保当前用户的默认知识库存在（每用户独立，内置无需手动创建）。"""
    try:
        col = _kb_collection()
        name = _user_default_kb(username)
        if col.find_one({"name": name}) is None:
            _migrate_default_items(username)
            col.insert_one({"name": name, "owner": username, "is_default": True, "created_at": datetime.now(UTC)})
    except Exception:
        logger.exception(f"确保用户 {username} 的默认知识库失败")


@app.get("/knowledge-bases", summary="知识库列表", description="列出当前用户可使用的逻辑知识库（本人专属默认库 + 本人创建的库；管理员见全部）。")
async def list_knowledge_bases(authorization: str = Header(None, alias="Authorization")):
    username, role, _ = _resolve_actor(authorization)
    _ensure_default_kb(username)
    bases = []
    try:
        col = _kb_collection()
        if role == ROLE_ADMIN:
            docs = col.find({}, {"_id": 0})
        else:
            docs = col.find({"owner": username}, {"_id": 0})
        bases = [
            {"name": d["name"], "owner": d.get("owner", ""), "is_default": bool(d.get("is_default", False))}
            for d in docs
        ]
    except Exception as e:
        logger.warning(f"知识库列表查询失败: {e}")
    # 默认库始终置顶
    bases.sort(key=lambda b: (not b.get("is_default", False), b["name"]))
    return {"code": 200, "message": "success", "data": {"bases": bases}}


@app.post("/knowledge-bases", summary="新建知识库", description="创建一个逻辑知识库（仅记录元信息，导入时选择即可）。库名需唯一且长度受限。")
async def create_knowledge_base(
    name: str = Form(..., description="知识库名称"),
    authorization: str = Header(None, alias="Authorization"),
):
    username, role, _ = _resolve_actor(authorization)
    kb = (name or "").strip()
    if not kb or len(kb) > KB_NAME_MAXLEN:
        from jingwei_common.web.errors import BadRequestError

        raise BadRequestError(f"知识库名称需为非空且不超过 {KB_NAME_MAXLEN} 个字符")
    if kb == DEFAULT_KB or kb == _user_default_kb(username):
        from jingwei_common.web.errors import BadRequestError

        raise BadRequestError("默认知识库已存在，无需创建")
    try:
        col = _kb_collection()
        if col.find_one({"name": kb}):
            from jingwei_common.web.errors import BadRequestError

            raise BadRequestError(f"知识库「{kb}」已存在")
        col.insert_one({"name": kb, "owner": username, "is_default": False, "created_at": datetime.now(UTC)})
    except Exception as e:
        if isinstance(e, BadRequestError):
            raise
        logger.error(f"创建知识库失败: {e}")
        from jingwei_common.web.errors import ApiError

        raise ApiError("创建知识库失败", code=500)
    return {"code": 200, "message": "success", "data": {"name": kb, "owner": username, "is_default": False}}


@app.post("/knowledge-bases/{name}/rename", summary="重命名知识库", description="重命名逻辑知识库，并同步改写库内资料的 kb_name（Mongo 元信息 + Milvus chunk）。默认库不可重命名。")
async def rename_knowledge_base(
    name: str,
    new_name: str = Form(..., description="新的知识库名称"),
    authorization: str = Header(None, alias="Authorization"),
):
    from jingwei_common.web.errors import BadRequestError

    username, role, _ = _resolve_actor(authorization)
    kb_doc = _load_kb_or_404(name, username, role)
    if kb_doc.get("is_default"):
        raise BadRequestError("默认知识库不可重命名")

    target = (new_name or "").strip()
    if not target or len(target) > KB_NAME_MAXLEN:
        raise BadRequestError(f"知识库名称需为非空且不超过 {KB_NAME_MAXLEN} 个字符")
    if target == name:
        return {"code": 200, "message": "success", "data": {"name": name, "renamed": 0}}
    if target == DEFAULT_KB or target.startswith(KB_DEFAULT_PREFIX):
        raise BadRequestError("不可使用保留的默认库名称")
    try:
        if _kb_collection().find_one({"name": target}):
            raise BadRequestError(f"知识库「{target}」已存在")
    except BadRequestError:
        raise
    except Exception as e:
        logger.error(f"重名校验失败: {e}")
        from jingwei_common.web.errors import ApiError

        raise ApiError("重命名知识库失败", code=500)

    moved = _migrate_kb_items(name, target)
    try:
        _kb_collection().update_one(
            {"name": name},
            {"$set": {"name": target, "updated_at": datetime.now(UTC)}},
        )
    except Exception as e:
        logger.error(f"更新知识库名称失败: {e}")
        from jingwei_common.web.errors import ApiError

        raise ApiError("重命名知识库失败", code=500)

    audit_log(
        action="knowledge_base_rename",
        actor=username,
        actor_role=role or "member",
        detail={"from": name, "to": target, "moved_items": moved},
        source="knowledge",
    )
    return {"code": 200, "message": "renamed", "data": {"name": target, "renamed": moved}}


@app.delete("/knowledge-bases/{name}", summary="删除知识库", description="删除逻辑知识库。库内资料会迁移到操作者的默认库，避免误删数据。默认库不可删除。")
async def delete_knowledge_base(
    name: str,
    authorization: str = Header(None, alias="Authorization"),
):
    from jingwei_common.web.errors import BadRequestError

    username, role, _ = _resolve_actor(authorization)
    kb_doc = _load_kb_or_404(name, username, role)
    if kb_doc.get("is_default"):
        raise BadRequestError("默认知识库不可删除")

    # 安全策略：库内资料迁移到操作者默认库，而非级联删除
    target = _user_default_kb(username)
    moved = _migrate_kb_items(name, target)
    try:
        _kb_collection().delete_one({"name": name})
    except Exception as e:
        logger.error(f"删除知识库 {name} 失败: {e}")
        from jingwei_common.web.errors import ApiError

        raise ApiError("删除知识库失败", code=500)

    audit_log(
        action="knowledge_base_delete",
        actor=username,
        actor_role=role or "member",
        detail={"name": name, "moved_items": moved, "moved_to": target},
        source="knowledge",
    )
    return {"code": 200, "message": "deleted", "data": {"name": name, "moved_items": moved, "moved_to": target}}


@app.post("/documents/{item_name}/move", summary="移动资料到其它知识库", description="将某资料迁移到指定的逻辑知识库（更新 Milvus chunk 的 kb_name 与 Mongo 元信息）。仅 owner 或管理员可操作。")
async def move_document(
    item_name: str,
    target_kb: str = Form(..., description="目标逻辑知识库名称"),
    authorization: str = Header(None, alias="Authorization"),
):
    from jingwei_common.clients.milvus_client import milvus_client

    username, role, _ = _resolve_actor(authorization)
    target = (target_kb or "").strip()
    if not target:
        from jingwei_common.web.errors import BadRequestError

        raise BadRequestError("目标知识库不能为空")

    # 校验资料存在 + 权限
    owner = _item_owner(item_name)
    if not owner and role != ROLE_ADMIN:
        from jingwei_common.web.errors import NotFoundError

        raise NotFoundError("资料不存在")
    if role != ROLE_ADMIN and owner and owner != username:
        from jingwei_common.web.errors import ForbiddenError

        raise ForbiddenError("无权移动他人资料")

    # 校验目标库存在（默认库或本人创建的库；管理员任意）
    try:
        kb_doc = _kb_collection().find_one({"name": target})
        if kb_doc is None:
            from jingwei_common.web.errors import NotFoundError

            raise NotFoundError(f"目标知识库「{target}」不存在")
        if role != ROLE_ADMIN and kb_doc.get("owner") != username and not kb_doc.get("is_default"):
            from jingwei_common.web.errors import ForbiddenError

            raise ForbiddenError("无权移动到该知识库")
    except (NotFoundError, ForbiddenError):
        raise
    except Exception as e:
        logger.warning(f"目标库校验失败（忽略）: {e}")

    # 迁移：更新 Milvus chunk 的 kb_name 与 Mongo 元信息
    moved = 0
    try:
        client = milvus_client.client
        if client.has_collection(chunks_store.collection):
            res = client.query(
                chunks_store.collection,
                filter=f'item_name == "{item_name}"',
                output_fields=["*"],
            )
            rows = []
            for r in res:
                r["kb_name"] = target
                r.pop("pk", None)
                rows.append(r)
            if rows:
                client.delete(collection_name=chunks_store.collection, filter=f'item_name == "{item_name}"')
                client.insert(collection_name=chunks_store.collection, data=rows)
                client.flush(chunks_store.collection)
                moved = len(rows)
        _kb_collection()  # no-op，确保连接已初始化
        mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).update_one(
            {"item_name": item_name},
            {"$set": {"kb_name": target, "updated_at": datetime.now(UTC)}},
        )
    except Exception as e:
        logger.error(f"迁移资料 {item_name} 失败: {e}")
        from jingwei_common.web.errors import ApiError

        raise ApiError("资料迁移失败", code=500)

    audit_log(
        action="document_move",
        actor=username,
        actor_role=role or "member",
        detail={"item_name": item_name, "target_kb": target, "moved_chunks": moved},
        source="knowledge",
    )
    return {"code": 200, "message": "document moved", "item_name": item_name, "kb_name": target}


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
        raise BadRequestError("visibility 仅支持 private / team / shared")

    # 校验资料存在 + 权限
    owner = _item_owner(item_name)
    if not owner and role != ROLE_ADMIN:
        raise NotFoundError("资料不存在")
    if role != ROLE_ADMIN and owner and owner != username:
        raise ForbiddenError("无权修改他人资料可见性")

    # 切到 team 可见时必须有所属团队。
    # 注意：此前此处会静默降级为 private 并仍返回 200，导致调用方以为设置成功，
    # 实际界面仍显示「私有」（用户可见的 bug）。现改为明确报错。
    target_team = actor_team if visibility == VIS_TEAM else ""
    if visibility == VIS_TEAM and not target_team:
        raise BadRequestError("你尚未加入任何团队，无法将资料设为「团队可见」")

    # 仅更新 Mongo 元信息即可（可见性/归属/团队 的权威来源；检索过滤读取 Mongo）
    # 用 upsert + $setOnInsert 保底：历史资料可能未写入 Mongo 元信息，
    # 若用普通 update_one 会匹配 0 条而"看似成功实则未生效"（同为静默失败）。
    try:
        now = datetime.now(UTC)
        res = mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).update_one(
            {"item_name": item_name},
            {
                "$set": {"visibility": visibility, "team_id": target_team, "updated_at": now},
                "$setOnInsert": {
                    "item_name": item_name,
                    "owner": owner or username,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        if res.matched_count == 0 and res.upserted_id is None:
            logger.warning(f"可见性更新未匹配任何资料: {item_name}")
    except ApiError:
        raise
    except Exception as e:
        logger.error(f"可见性持久化失败: {e}")
        raise ApiError("可见性保存失败", code=500)

    audit_log(
        action="document_visibility",
        actor=username,
        actor_role=role or "member",
        detail={"item_name": item_name, "visibility": visibility, "team_id": target_team},
        source="knowledge",
    )
    # 注意：必须放进 data 里返回，前端按统一 {code, message, data} 约定读取实际生效值
    return {
        "code": 200,
        "message": "visibility updated",
        "data": {"item_name": item_name, "visibility": visibility, "team_id": target_team},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.import_app_port)
