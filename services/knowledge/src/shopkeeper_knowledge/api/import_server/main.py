"""
导入服务 HTTP 入口：文件上传、后台 LangGraph 执行、状态查询、演示页面。
"""
import shutil
import uuid
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from shopkeeper_common.config import settings
from shopkeeper_common.config.common import PROJECT_ROOT
from shopkeeper_common.logging import logger
from shopkeeper_common.web.task_utils import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    add_done_task,
    add_running_task,
    get_done_task_list,
    get_running_task_list,
    get_task_status,
    update_task_status,
)
from starlette.middleware.cors import CORSMiddleware

from shopkeeper_knowledge.api.schemas.import_schema import ImportStatusResponse, UploadResponse
from shopkeeper_knowledge.process.import_chain.main_graph import kb_import_app
from shopkeeper_knowledge.process.import_chain.state import get_default_state

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


@app.get("/html")
def import_html():
    """返回导入演示页面。"""
    html_path = Path(__file__).resolve().parents[2] / "process" / "import_chain" / "page" / "import.html"
    return FileResponse(path=html_path, media_type=guess_type(html_path.name)[0])


def run_graph_task(task_id: str, local_dir: str, local_file_path: str):
    """后台执行 LangGraph 全流程，实时更新任务状态。"""
    try:
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        logger.info(f"[{task_id}] 开始执行LangGraph全流程，本地文件路径：{local_file_path}")

        init_state = get_default_state()
        init_state["task_id"] = task_id
        init_state["local_dir"] = local_dir
        init_state["local_file_path"] = local_file_path

        for event in kb_import_app.stream(init_state):
            for node_name in event.keys():
                logger.info(f"[{task_id}] LangGraph节点执行完成：{node_name}")
                add_done_task(task_id, node_name)

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(f"[{task_id}] LangGraph全流程执行完毕，任务完成")
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        logger.error(f"[{task_id}] LangGraph全流程执行失败：{e}", exc_info=True)


@app.post("/upload", summary="文件上传接口", description="支持多文件批量上传")
async def upload_files(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
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
        )

    return UploadResponse(
        code=200,
        message=f"Files uploaded successfully, total: {len(files)}",
        task_ids=task_ids,
    )


@app.get("/status/{task_id}", summary="任务状态查询", response_model=ImportStatusResponse)
async def get_task_progress(task_id: str):
    status = get_task_status(task_id)
    done_list = get_done_task_list(task_id)
    running_list = get_running_task_list(task_id)
    logger.info(f"[{task_id}] 任务状态查询，当前状态：{status}，已完成节点：{done_list}")
    return ImportStatusResponse(
        code=200,
        task_id=task_id,
        status=status,
        done_list=done_list,
        running_list=running_list,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.import_app_port)
