"""
查询服务 HTTP 入口：查询接口、SSE 流式输出、演示页面。
"""
import uuid
from mimetypes import guess_type
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from shopkeeper_common.config import settings
from shopkeeper_common.config.common import PROJECT_ROOT
from shopkeeper_common.logging import logger
from shopkeeper_common.web.sse_utils import SSEEvent, create_sse_queue, sse_generator
from shopkeeper_common.web.task_utils import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    add_done_task,
    add_running_task,
    get_task_result,
    set_task_result,
    update_task_status,
)
from sse_starlette.sse import EventSourceResponse

from shopkeeper_query.api.schemas.query_schema import (
    QueryRequest,
    QueryResponse,
    SessionRenameRequest,
)
from shopkeeper_query.infra.persistence.history_repository import history_repo
from shopkeeper_query.process.query_chain.main_graph import kb_query_app

load_dotenv()

app = FastAPI(
    title=settings.query_app_name,
    description="企业化 RAG 查询服务，负责问题重新措辞、混合检索、重排、LLM 作答与流式输出。",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins.split(",")) if settings.cors_origins != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_query_task(
    task_id: str,
    session_id: str,
    query: str,
    item_name: str | None,
    need_stream: bool,
    model: str | None = None,
    username: str | None = None,
):
    """后台执行查询链全流程。"""
    try:
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        init_state = {
            "task_id": task_id,
            "session_id": session_id,
            "username": username or "guest",
            "query": query,
            "user_query": query,
            "item_name": item_name or "",
            "model": model or "",
            "rephrased_query": "",
            "keywords": [],
            "vector_documents": [],
            "hyde_documents": [],
            "web_documents": [],
            "rrf_documents": [],
            "rerank_documents": [],
            "llm_output": "",
            "delta_queue": None,
            "need_stream_output": need_stream,
        }
        from shopkeeper_common.config.lm_config import lm_config as _lm

        from shopkeeper_query.process.query_chain.services.query_rag_service import _stream_text

        # mock 快捷路径：跳过 LangGraph 全图（fan-in 抖动耗时大），直接生成模拟回答并流式
        if _lm.mock:
            for n in ["node_query_rewrite", "node_query_vector", "node_query_hyde",
                      "node_query_mcp", "node_query_rrf", "node_query_rerank",
                      "node_query_rag", "node_query_save"]:
                add_done_task(task_id, n)
            mock_answer = (
                f"这是模拟回答（LLM_MOCK 模式）。您的问题是：{query}。"
                "当前为人工测试模式，前端完整链路（SSE 流式 / 持久化 / 会话）已可正常验证。"
                "关闭 LLM_MOCK 后即调用真实本地模型。"
            )
            _stream_text(session_id, mock_answer, need_stream, mock=True)
            final = {"llm_output": mock_answer, "session_id": session_id, "query": query}
        else:
            final = None
            for event in kb_query_app.stream(init_state):
                for node_name in event.keys():
                    add_done_task(task_id, node_name)
                    final = event[node_name]

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        result = final or {}
        # 保存最终结果到 task_result（供前端 SSE 失败时通过 /task/result 兜底拉取）
        set_task_result(
            task_id,
            {
                "llm_output": result.get("llm_output", ""),
                "title": query[:30],
            },
        )
        # 推送最终答案（SSE 队列按 session_id 关联，须用 session_id 推送）
        if need_stream:
            from shopkeeper_common.web.sse_utils import push_to_session

            push_to_session(session_id, SSEEvent.FINAL, {"answer": result.get("llm_output", "")})
            push_to_session(session_id, SSEEvent.CLOSE, {})
        logger.info(f"[{task_id}] 查询链执行完成")
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        logger.error("[%s] 查询链执行失败: %s", task_id, e, exc_info=True)
        if need_stream:
            from shopkeeper_common.web.sse_utils import push_to_session

            push_to_session(session_id, SSEEvent.ERROR, {"error": str(e)})
            push_to_session(session_id, SSEEvent.CLOSE, {})


@app.get("/health")
async def health():
    """健康检查端点（供容器编排探活）。"""
    return {"code": 0, "message": "ok", "data": {"status": "up", "service": settings.query_app_name}}


@app.post("/chat/query", response_model=QueryResponse)
async def chat_query(req: QueryRequest):
    """接收查询请求，后台执行查询链，返回 task_id。"""
    session_id = req.session_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    add_running_task(task_id, "chat_query")

    # 预建 session 的 SSE 队列，确保查询链推送（delta/final）即使前端尚未连上也不丢失
    if req.need_stream_output:
        create_sse_queue(session_id)

    import threading

    t = threading.Thread(
        target=run_query_task,
        args=(
            task_id,
            session_id,
            req.query,
            req.item_name,
            req.need_stream_output,
            req.model,
            req.username,
        ),
        daemon=True,
    )
    t.start()

    return QueryResponse(
        code=200,
        message="查询任务已提交",
        data={"task_id": task_id, "session_id": session_id},
    )


@app.get("/models")
async def list_models():
    """返回可用的对话模型列表（供前端选择）。

    本地 provider 时动态拉取本地模型（Ollama 等），DashScope 时返回内置列表。
    """
    from shopkeeper_common.ai.chat import list_models as get_models
    from shopkeeper_common.config.lm_config import lm_config

    models = get_models()
    default = lm_config.active_default_model
    return QueryResponse(
        code=200,
        message="success",
        data={"models": models, "default": default, "provider": lm_config.provider},
    )


@app.get("/chat/stream/{session_id}")
async def chat_stream(session_id: str, request: Request):
    """SSE 流式输出（按 session_id 关联任务队列）。"""
    create_sse_queue(session_id)
    return EventSourceResponse(sse_generator(session_id, request))


@app.get("/task/result/{task_id}")
async def task_result(task_id: str):
    """查询任务最终结果与进度。"""
    return QueryResponse(code=200, message="success", data=get_task_result(task_id))


@app.get("/sessions")
async def list_sessions_endpoint(username: str | None = None):
    """返回会话列表（按更新时间倒序）。可传 username 过滤。"""
    sessions = history_repo.list_sessions(username=username, limit=100)
    # 转成前端友好格式（含消息数）
    data = {
        "sessions": [
            {
                "session_id": s["session_id"],
                "title": s["title"],
                "updated_at": s["updated_at"].isoformat()
                if hasattr(s["updated_at"], "isoformat")
                else s["updated_at"],
                "meta": s["meta"],
            }
            for s in sessions
        ]
    }
    return QueryResponse(code=200, message="success", data=data)


@app.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str):
    """返回某会话的历史消息（按时间升序）。"""
    messages = history_repo.get_history(session_id, limit=200)
    return QueryResponse(code=200, message="success", data={"session_id": session_id, "messages": messages})


@app.patch("/sessions/{session_id}")
async def rename_session_endpoint(session_id: str, req: SessionRenameRequest):
    """重命名会话标题。"""
    history_repo.rename_session(session_id, req.title)
    return QueryResponse(code=200, message="success", data={"session_id": session_id, "title": req.title})


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """删除会话及其消息。"""
    history_repo.clear_session(session_id)
    return QueryResponse(code=200, message="success", data={"session_id": session_id})


@app.get("/html")
def chat_html():
    """返回查询演示页面。"""
    html_path = Path(__file__).resolve().parents[2] / "process" / "query_chain" / "page" / "chat.html"
    return FileResponse(path=html_path, media_type=guess_type(html_path.name)[0])


@app.get("/", include_in_schema=False)
def react_index():
    """返回 React 前端主界面（Vite 构建产物）。"""
    html_path = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    return FileResponse(path=html_path, media_type="text/html")


# 挂载 React 静态资源（frontend/dist 构建产物，供 /assets/* 引用）
_react_dist = PROJECT_ROOT / "frontend" / "dist"
if _react_dist.exists():
    app.mount("/assets", StaticFiles(directory=_react_dist / "assets"), name="frontend-assets")


@app.middleware("http")
async def _no_cache_static(request, call_next):
    """为前端 dist 资源（/ 与 /assets/*）添加 no-cache 头，避免浏览器缓存旧版本。"""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/assets"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.query_app_port)
