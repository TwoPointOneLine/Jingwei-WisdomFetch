"""保存对话服务（兼容再导出）：核心实现沿用原持久化逻辑。"""
from jingwei_common.logging import logger

from jingwei_query.infra.persistence.history_repository import history_repo
from jingwei_query.process.query_chain.state import QueryGraphState


def save_conversation(state: QueryGraphState) -> QueryGraphState:
    """将用户问题与 LLM 答案写入历史存储。"""
    session_id = state.get("session_id", "")
    user_query = state.get("user_query") or state["query"]
    answer = state.get("llm_output", "")

    if session_id:
        username = state.get("username") or "guest"
        anon_id = state.get("anon_id")
        history_repo.create_session_if_not_exists(
            session_id,
            {"username": username, "anon_id": anon_id if username == "guest" else None},
        )
        # 登录用户首次在 guest 会话中发消息 → 归并到本人（保留历史、清除 anon_id），
        # 解决「登录后看到未登录时会话」且不同未登录访客互不共享。
        if username != "guest":
            history_repo.reassign_session(session_id, username)
        meta = {"username": username, "title": (state.get("rephrased_query") or user_query)[:40]}
        if username == "guest":
            meta["anon_id"] = anon_id
        history_repo.update_session_meta(session_id, meta)
        history_repo.append_message(session_id, "user", user_query)
        history_repo.append_message(session_id, "assistant", answer)
        logger.info(f"对话已保存: session={session_id}, user={username}, anon={anon_id}")
    return state
