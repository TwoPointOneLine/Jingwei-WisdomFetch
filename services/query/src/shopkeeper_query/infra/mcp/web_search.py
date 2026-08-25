"""
联网搜索 MCP 封装（infra 层）。

基于 openai-agents 的 MCPServerStreamableHttp 调用 DashScope WebSearch MCP，
返回结构化网页结果列表 [{title, url, snippet}]。
"""
import asyncio
import json

from shopkeeper_common.config.bailian_mcp_config import mcp_config
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger, step_log


async def _search_web_async(query: str, count: int = 5) -> list[dict]:
    """异步调用 DashScope WebSearch MCP 工具。"""
    from agents.mcp import MCPServerStreamableHttp

    server = MCPServerStreamableHttp(
        name="search_mcp",
        client_session_timeout_seconds=300,
        params={
            "url": mcp_config.mcp_base_url,
            "headers": {"Authorization": lm_config.api_key},
            "timeout": 300,
            "sse_read_timeout": 300,
        },
    )
    try:
        await server.connect()
        logger.info("MCP 联网搜索连接成功")
        result = await server.call_tool(
            tool_name="bailian_web_search",
            arguments={"query": query, "count": count},
        )
        text = result.content[0].text
        pages = json.loads(text).get("pages", [])
        # 清洗：去空白、过滤 snippet 空值
        cleaned = []
        for p in pages:
            title = (p.get("title") or "").strip()
            url = (p.get("url") or "").strip()
            snippet = (p.get("snippet") or "").strip()
            if not snippet:
                continue
            cleaned.append({"title": title, "url": url, "snippet": snippet})
        return cleaned
    finally:
        await server.cleanup()


@step_log("web_search")
def search_web_documents(query: str, count: int = 5) -> list[dict]:
    """
    同步入口：联网检索。
    :param query: 标准化检索问句
    :param count: 返回条数
    :return: 结构化网页结果列表
    """
    return asyncio.run(_search_web_async(query, count=count))
