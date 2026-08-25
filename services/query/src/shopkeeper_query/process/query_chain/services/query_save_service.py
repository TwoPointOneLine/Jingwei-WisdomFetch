"""保存对话服务（兼容再导出）：核心实现沿用原持久化逻辑。"""
from shopkeeper_common.logging import logger

from shopkeeper_query.infra.persistence.history_repository import history_repo
from shopkeeper_query.process.query_chain.state import QueryGraphState


def save_conversation(state: QueryGraphState) -> QueryGraphState:
    """将用户问题与 LLM 答案写入历史存储。"""
    session_id = state.get("session_id", "")
    user_query = state.get("user_query") or state["query"]
    answer = state.get("llm_output", "")

    if session_id:
        username = state.get("username") or "guest"
        history_repo.create_session_if_not_exists(session_id, {"username": username})
        history_repo.update_session_meta(
            session_id,
            {"username": username, "title": (state.get("rephrased_query") or user_query)[:40]},
        )
        history_repo.append_message(session_id, "user", user_query)
        history_repo.append_message(session_id, "assistant", answer)
        logger.info(f"对话已保存: session={session_id}, user={username}")
    return state
