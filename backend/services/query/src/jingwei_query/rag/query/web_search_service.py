"""
联网检索服务：调用联网搜索 MCP 获取补充资料。

mock 模式或 MCP 不可用时返回空列表，主流程不依赖外网结果。
"""
from jingwei_common.config.lm_config import lm_config
from jingwei_common.logging import logger

from jingwei_query.infra.mcp.web_search import search_web_documents


def web_search(state) -> dict:
    """
    取出 rephrased_query（回退 query）调用联网搜索，回写 web_documents。

    受 lm_config.web_search_enabled 总开关控制（FR-QA-06）：默认关闭，
    保证回答仅基于已导入的内部资料；开启时返回的每条结果带 external=True 标记，
    供重排与引用溯源识别外网来源的「可信度」属性。
    """
    if lm_config.mock or not lm_config.web_search_enabled:
        return {"web_documents": []}

    query = state.get("rephrased_query") or state["query"]
    try:
        pages = search_web_documents(query, count=5)
    except Exception as e:
        logger.warning(f"联网搜索失败（不影响主流程）: {e}")
        pages = []
    for p in pages:
        p["external"] = True
    logger.info(f"网页检索 {len(pages)} 条")
    return {"web_documents": pages}
