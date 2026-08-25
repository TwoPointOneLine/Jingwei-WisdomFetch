"""
联网检索服务：调用联网搜索 MCP 获取补充资料。

mock 模式或 MCP 不可用时返回空列表，主流程不依赖外网结果。
"""
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger

from shopkeeper_query.infra.mcp.web_search import search_web_documents


def web_search(state) -> dict:
    """
    取出 rephrased_query（回退 query）调用联网搜索，回写 web_documents。
    """
    if lm_config.mock:
        return {"web_documents": []}

    query = state.get("rephrased_query") or state["query"]
    try:
        pages = search_web_documents(query, count=5)
    except Exception as e:
        logger.warning(f"联网搜索失败（不影响主流程）: {e}")
        pages = []
    logger.info(f"网页检索 {len(pages)} 条")
    return {"web_documents": pages}
