"""
重新措辞服务（兼容再导出）：核心实现见 app.rag.query 主体确认/检索层。

原入口处对查询做 history 感知的改写，核心能力已由 app.rag.query 提供；
此处保留与原 state 契约一致的适配入口，委托给 item_name_confirm + 改写逻辑。
"""
from jingwei_common.ai.providers import llm_provider
from jingwei_common.config.rag_config import rag_config
from jingwei_common.logging import logger

from jingwei_query.infra.persistence.history_repository import history_repo
from jingwei_query.rag.query.history_context import build_history_text
from jingwei_query.process.query_chain.state import QueryGraphState


def rewrite_query(state: QueryGraphState) -> QueryGraphState:
    """基于历史把用户口语化问题改写为标准检索问句，回写 rephrased_query。"""
    query = state["query"]
    session_id = state.get("session_id", "")
    user_query = state.get("user_query") or query

    # 优先复用 node_query_history 已读取的历史，缺失时（如单节点调用）自行兜底读取
    history = state.get("history") or []
    if not history and session_id:
        try:
            history = history_repo.get_history(session_id, limit=rag_config.rewrite_history_limit) or []
        except Exception as e:
            logger.warning(f"读取对话历史失败: {e}")
            history = []
    history_text = build_history_text(history, rag_config.history_turns)

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
