"""
重新措辞服务（兼容再导出）：核心实现见 app.rag.query 主体确认/检索层。

原入口处对查询做 history 感知的改写，核心能力已由 app.rag.query 提供；
此处保留与原 state 契约一致的适配入口，委托给 item_name_confirm + 改写逻辑。
"""
from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.logging import logger

from shopkeeper_query.infra.persistence.history_repository import history_repo
from shopkeeper_query.process.query_chain.state import QueryGraphState


def rewrite_query(state: QueryGraphState) -> QueryGraphState:
    """基于历史把用户口语化问题改写为标准检索问句，回写 rephrased_query。"""
    query = state["query"]
    session_id = state.get("session_id", "")
    user_query = state.get("user_query") or query

    history = history_repo.get_history(session_id, limit=10) if session_id else []
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history) if history else "（无历史）"

    prompt = (
        "你需要将用户的口语化问题，结合对话历史，改写成一条标准、清晰、适合向量检索的检索问句。\n"
        "只返回改写后的问句，不要解释。\n\n"
        f"对话历史：\n{history_text}\n\n"
        f"用户原问题：{user_query}"
    )
    try:
        model = llm_provider.chat()
        resp = model.invoke(prompt)
        rephrased = (getattr(resp, "content", "") or "").strip()
        if not rephrased:
            rephrased = user_query
    except Exception as e:
        logger.warning(f"重新措辞失败，回退原问题: {e}")
        rephrased = user_query

    state["rephrased_query"] = rephrased
    logger.info(f"重新措辞: {user_query} -> {rephrased}")
    return state
