"""
查询服务 HTTP 入口：查询接口、SSE 流式输出。
"""
import uuid
from datetime import UTC

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from jingwei_common.audit import audit_log
from jingwei_common.auth import auth_client
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.config import settings
from jingwei_common.constants import COLLECTION_CHAT_FEEDBACK
from jingwei_common.logging import logger
from jingwei_common.web.sse_utils import SSEEvent, create_sse_queue, sse_generator
from jingwei_common.web.task_utils import (
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

from jingwei_query.api.schemas.query_schema import (
    FeedbackRequest,
    QueryRequest,
    QueryResponse,
    SessionRenameRequest,
)
from jingwei_query.infra.persistence.history_repository import history_repo
from jingwei_query.process.query_chain.main_graph import kb_query_app

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
    anon_id: str | None = None,
    role: str | None = None,
    team_id: str = "",
):
    """后台执行查询链全流程。"""
    try:
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        init_state = {
            "task_id": task_id,
            "session_id": session_id,
            "username": username or "guest",
            "user_role": role or "",
            "user_team_id": team_id or "",
            "anon_id": anon_id,
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
        from jingwei_common.config.lm_config import lm_config as _lm

        from jingwei_query.process.query_chain.services.query_rag_service import _stream_text

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
        citations = result.get("citations", [])
        # 保存最终结果到 task_result（供前端 SSE 失败时通过 /task/result 兜底拉取）
        set_task_result(
            task_id,
            {
                "llm_output": result.get("llm_output", ""),
                "citations": citations,
                "title": query[:30],
            },
        )
        # 推送最终答案（SSE 队列按 session_id 关联，须用 session_id 推送）
        if need_stream:
            from jingwei_common.web.sse_utils import push_to_session

            # FR-CITE-02：随答案回传结构化来源引用，前端可展开可信标记
            push_to_session(
                session_id,
                SSEEvent.FINAL,
                {"answer": result.get("llm_output", ""), "citations": citations},
            )
            push_to_session(session_id, SSEEvent.CLOSE, {})
        logger.info(f"[{task_id}] 查询链执行完成")
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        logger.error("[%s] 查询链执行失败: %s", task_id, e, exc_info=True)
        if need_stream:
            from jingwei_common.web.sse_utils import push_to_session

            push_to_session(session_id, SSEEvent.ERROR, {"error": str(e)})
            push_to_session(session_id, SSEEvent.CLOSE, {})


@app.get("/health")
async def health():
    """健康检查端点（供容器编排探活）。"""
    return {"code": 0, "message": "ok", "data": {"status": "up", "service": settings.query_app_name}}


@app.post("/chat/query", response_model=QueryResponse)
async def chat_query(req: QueryRequest, request: Request):
    """接收查询请求，后台执行查询链，返回 task_id。"""
    session_id = req.session_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    add_running_task(task_id, "chat_query")

    # 未登录访客的匿名 ID：优先取请求体，回退到 X-Anon-Id 头（SSE 等场景）
    anon_id = req.anon_id or request.headers.get("X-Anon-Id") or ""

    # 预建 session 的 SSE 队列，确保查询链推送（delta/final）即使前端尚未连上也不丢失
    if req.need_stream_output:
        create_sse_queue(session_id)

    import threading

    # 服务端可信解析角色与团队（用于检索隔离，不信任客户端传参）
    actor_role = ""
    actor_team = ""
    token = auth_client.extract_token(request.headers.get("Authorization"))
    if token:
        try:
            actor_username = auth_client.validate_token(token)
        except Exception:
            actor_username = None
        if actor_username:
            try:
                actor_role = auth_client.get_user_role(actor_username) or ""
            except Exception:
                actor_role = ""
            try:
                actor_team = auth_client.get_user_team(actor_username) or ""
            except Exception:
                actor_team = ""

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
            anon_id,
            actor_role,
            actor_team,
        ),
        daemon=True,
    )
    t.start()

    # NFR-SEC-04：问答查询审计留痕（actor 取请求体用户名或匿名 ID）
    audit_log(
        action="query_chat",
        actor=req.username or anon_id or "guest",
        actor_role="",
        detail={"task_id": task_id, "session_id": session_id, "query_len": len(req.query)},
        source="query",
    )

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
    from jingwei_common.ai.chat import list_models as get_models
    from jingwei_common.config.lm_config import lm_config

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


def _resolve_owner(request: Request) -> tuple[str, str]:
    """从请求解析归属身份（服务端可信，不信任客户端传参）。

    返回 (username, anon_id)：
    - 携带有效 token → username=真实用户名，anon_id=""（按用户名隔离）
    - 未登录（无 token 或无效）→ username="guest"，anon_id=请求中的匿名 ID
      （X-Anon-Id 头或 ?anon_id=），用于把 guest 会话按单个浏览器隔离，
      确保不同未登录访客互不看到彼此的对话。
    """
    token = auth_client.extract_token(request.headers.get("Authorization"))
    if not token:
        token = request.query_params.get("token", "")
    username = auth_client.validate_token(token) if token else None
    if username:
        return username, ""
    anon_id = request.headers.get("X-Anon-Id") or request.query_params.get("anon_id") or ""
    return "guest", anon_id


@app.get("/sessions")
async def list_sessions_endpoint(request: Request):
    """返回当前用户（或当前访客）的会话列表（按更新时间倒序）。

    身份服务端从 token / 匿名 ID 解析：登录用户只看自己；未登录访客只看自己
    浏览器（anon_id）下的 guest 会话。不再接受客户端 username 参数，杜绝越权。
    """
    username, anon_id = _resolve_owner(request)
    sessions = history_repo.list_sessions(
        username=username, anon_id=anon_id or None, limit=100
    )
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


@app.post("/sessions/claim")
async def claim_sessions_endpoint(request: Request):
    """登录即归并：把本浏览器（anon_id）下遗留的 guest 会话批量归并到当前登录用户。

    用于解决「切换账号前未登录开的会话、登录后没发消息就退出导致登录态看不到」。
    仅接受有效 token（登录态），anon_id 从请求体或 X-Anon-Id 头读取。
    """
    username, _ = _resolve_owner(request)
    if username == "guest":
        return QueryResponse(code=401, message="请先登录", data=None)
    anon_id = ""
    try:
        body = await request.json()
        anon_id = body.get("anon_id") or ""
    except Exception:  # noqa: BLE001 — 无 body 或非法 JSON 时回退到头
        anon_id = ""
    if not anon_id:
        anon_id = request.headers.get("X-Anon-Id") or ""
    claimed = history_repo.claim_guest_sessions(anon_id, username) if anon_id else 0
    return QueryResponse(
        code=200,
        message="success",
        data={"claimed": claimed, "username": username},
    )


@app.get("/sessions/{session_id}/messages")
async def session_messages(request: Request, session_id: str):
    """返回某会话的历史消息（按时间升序）。仅归属者可读取。"""
    username, anon_id = _resolve_owner(request)
    meta = history_repo.get_session_meta(session_id)
    if username != "guest":
        # 登录用户：仅能读自己名下的会话
        if meta.get("username") != username:
            return QueryResponse(code=403, message="无权访问该会话", data=None)
    else:
        # 未登录访客：仅能读自己 anon_id 下的 guest 会话
        if meta.get("username") != "guest" or meta.get("anon_id") != anon_id:
            return QueryResponse(code=403, message="无权访问该会话", data=None)
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


@app.post("/feedback")
async def feedback_endpoint(req: FeedbackRequest, request: Request):
    """接收用户对答案的满意度 / 纠错反馈（FR-COMP-05 可投诉/标识）。

    反馈归属服务端从 token / 匿名 ID 解析（不信任客户端传参），
    持久化到 MongoDB 的 COLLECTION_CHAT_FEEDBACK 集合，供后续合规审计与模型优化。
    """
    username, anon_id = _resolve_owner(request)
    from datetime import datetime

    doc = {
        "feedback_id": uuid.uuid4().hex,
        "session_id": req.session_id,
        "message_id": req.message_id,
        "rating": req.rating,
        "feedback_type": req.feedback_type,
        "content": req.content,
        "username": username if username != "guest" else "",
        "anon_id": anon_id,
        "created_at": datetime.now(UTC),
    }
    try:
        coll = mongo_client.get_collection(COLLECTION_CHAT_FEEDBACK)
        coll.insert_one(doc)
    except Exception as exc:  # noqa: BLE001 — 反馈写入失败不影响前端体验
        logger.warning(f"反馈写入失败: {exc}")
        return QueryResponse(code=200, message="反馈已记录（存储暂不可用）", data={"feedback_id": doc["feedback_id"]})
    return QueryResponse(code=200, message="success", data={"feedback_id": doc["feedback_id"]})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.query_app_port)
