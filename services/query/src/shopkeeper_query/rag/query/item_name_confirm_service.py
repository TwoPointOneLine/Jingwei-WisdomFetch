"""
主体确认服务：基于查询与历史，确认/补全本次检索的商品主体 item_name。

利用 LLM 从问题文本与对话历史中抽取或确认 item_name，回写供检索与入库过滤使用。
无法确认时回退为空字符串（由检索阶段退化为全量语义检索）。
"""
from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.logging import logger

from shopkeeper_query.infra.persistence.history_repository import history_repo


def confirm_item_name(state) -> dict:
    """
    根据 state.query / user_query / session_id 确认 item_name，回写 item_name。
    """
    query = state.get("query", "")
    user_query = state.get("user_query") or query
    session_id = state.get("session_id", "")

    history = history_repo.get_history(session_id, limit=5) if session_id else []
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history) if history else "（无历史）"

    prompt = (
        "请判断下面的用户问题涉及哪个『商品主体名称』（如型号/设备名）。"
        "如果能确定，只返回该名称；如果无法确定，只返回空字符串。不要解释。\n\n"
        f"对话历史：\n{history_text}\n\n用户问题：{user_query}"
    )
    try:
        model = llm_provider.chat()
        resp = model.invoke(prompt)
        item_name = (getattr(resp, "content", "") or "").strip()
    except Exception as e:
        logger.warning(f"主体确认失败，回退空: {e}")
        item_name = ""

    logger.info(f"主体确认: {user_query} -> {item_name}")
    return {"item_name": item_name}
