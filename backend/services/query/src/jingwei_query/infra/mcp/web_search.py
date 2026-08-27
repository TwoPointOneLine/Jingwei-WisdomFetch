"""
联网搜索 MCP 封装（infra 层）。

基于 openai-agents 的 MCPServerStreamableHttp 调用 DashScope WebSearch MCP，
返回结构化网页结果列表 [{title, url, snippet}]。

协议协商说明（历史坑，2026-08-25）
---------------------------------
已安装的 MCP Python SDK 为 v2，其 `MCPServerStreamableHttp` 默认 `mode="auto"`：
先以 `LATEST_MODERN_VERSION` (2025-06-18) 发送 `server/discover`，再 fallback 到
`initialize` 握手（同样携带 2025-06-18）。而 DashScope 的 WebSearch MCP 是一个
老版本 Streamable HTTP 服务，只理解 `2025-03-26`。它不识别 2025-06-18，于是在
discover/initialize 阶段直接返回 JSON-RPC 错误 `-32603` (Internal Error)。

- SDK 的 auto 策略把 "非 -32022" 的 MCPError 当成 legacy 信号，再去 `initialize`，
  但 initialize 内部硬编码的版本仍是 2025-06-18，所以老服务依旧回 -32603，最终
  `MCPError(-32603, 'Server returned an error response')` 向上抛出。
- 该 MCPError 往往被 anyio/asyncio 的 TaskGroup 包裹成 `ExceptionGroup`，导致
  `asyncio.run` 抛出未处理的 `BaseExceptionGroup`，整条查询链路崩溃。

修复手段：
1. 通过请求头 `Mcp-Protocol-Version: 2025-03-26` 固定协议版本（随 httpx 默认头带到
   每个 HTTP 请求，服务端按该头选版本应答），规避 2025-06-18 不被识别的问题。
2. 解包 `ExceptionGroup`，提取真正的 `MCPError` 并打印服务端返回的 code/message/data。
3. 连接失败时带退避重试；最终仍失败则记录日志并返回空结果，避免拖垮查询链路。
"""
import asyncio
import json
from contextlib import suppress

from jingwei_common.config.bailian_mcp_config import mcp_config
from jingwei_common.config.lm_config import lm_config
from jingwei_common.logging import logger, step_log

# DashScope WebSearch MCP 实际支持的握手协议版本。
# 固定该版本可避免 SDK v2（默认协商 2025-06-18）被老服务以 -32603 拒绝。
SUPPORTED_PROTOCOL_VERSION = "2025-03-26"

# 连接重试次数与退避（秒）。discover/initialize 偶发 -32603 时重试可恢复。
CONNECT_MAX_RETRIES = 2
CONNECT_RETRY_BACKOFF = 1.0


def _unwrap_mcp_error(exc: BaseException) -> "tuple[int | None, str | None, object | None]":
    """从异常（可能是 ExceptionGroup 包裹）中提取底层 MCPError 的 code/message/data。

    返回 (code, message, data)。若无法提取则返回 (None, None, None)。
    """
    candidates: list[BaseException] = [exc]
    # ExceptionGroup / BaseExceptionGroup 会包裹真实异常，递归取出所有叶子。
    group = exc
    while isinstance(group, (ExceptionGroup, BaseExceptionGroup)):
        inner = getattr(group, "exceptions", ())
        if not inner:
            break
        candidates = list(inner)
        # 继续向下钻取第一层嵌套，直到找到非 group 的异常。
        group = inner[0]

    best_code: int | None = None
    best_message: str | None = None
    best_data: object | None = None
    for e in candidates:
        # openai-agents 会把 MCPError 包进 UserError，真实错误在 __cause__/__context__。
        for leaf in (e, getattr(e, "__cause__", None), getattr(e, "__context__", None)):
            if leaf is None:
                continue
            code = getattr(leaf, "code", None)
            message = getattr(leaf, "message", None) or str(leaf)
            data = None
            data_fn = getattr(leaf, "data", None)
            if callable(data_fn):
                with suppress(Exception):
                    data = data_fn()
            if code is not None or "MCPError" in type(leaf).__name__ or "Server returned" in str(leaf):
                best_code = code if isinstance(code, int) else best_code
                best_message = message if isinstance(message, str) else best_message
                best_data = data if best_data is None else best_data
    return best_code, best_message, best_data


async def _connect_with_retry(server) -> None:
    """带退避重试的 connect；每次重试重建底层会话以规避偶发 -32603。"""
    last_exc: BaseException | None = None
    for attempt in range(CONNECT_MAX_RETRIES + 1):
        try:
            await server.connect()
            return
        except BaseException as e:  # noqa: BLE001 — 需捕获 MCPError / ExceptionGroup / UserError
            last_exc = e
            code, message, data = _unwrap_mcp_error(e)
            logger.warning(
                "MCP 联网搜索连接失败（第 %d/%d 次）：code=%s message=%s data=%s",
                attempt + 1,
                CONNECT_MAX_RETRIES + 1,
                code,
                message,
                data,
            )
            if attempt < CONNECT_MAX_RETRIES:
                await asyncio.sleep(CONNECT_RETRY_BACKOFF * (attempt + 1))
                # 清理上一轮可能残留的会话/连接，避免端口/连接状态复用导致再次失败。
                with suppress(Exception):
                    await server.cleanup()
                continue
    assert last_exc is not None
    raise last_exc


async def _search_web_async(query: str, count: int = 5) -> list[dict]:
    """异步调用 DashScope WebSearch MCP 工具。"""
    from agents.mcp import MCPServerStreamableHttp

    server = MCPServerStreamableHttp(
        name="search_mcp",
        client_session_timeout_seconds=300,
        params={
            "url": mcp_config.mcp_base_url,
            "headers": {
                # 固定协议版本：DashScope 老服务仅支持 2025-03-26，避免 SDK v2
                # 默认协商 2025-06-18 被服务端以 -32603 拒绝。
                "Mcp-Protocol-Version": SUPPORTED_PROTOCOL_VERSION,
                "Authorization": lm_config.api_key,
                "Content-Type": "application/json",
            },
            "timeout": 300,
            "client_session_timeout_seconds": 300,
            "sse_read_timeout": 300,
        },
    )
    try:
        await _connect_with_retry(server)
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

    即使 MCP 握手失败（-32603 / ExceptionGroup），也只记录日志并返回空列表，
    不让异常穿透 asyncio.run 拖垮整条查询链路。
    """
    try:
        return asyncio.run(_search_web_async(query, count=count))
    except (ExceptionGroup, BaseExceptionGroup) as eg:
        # 解包并日志化底层服务端错误，避免裸抛 ExceptionGroup 崩溃。
        code, message, data = _unwrap_mcp_error(eg)
        logger.error(
            "MCP 联网搜索失败（ExceptionGroup）：底层 code=%s message=%s data=%s；"
            "返回空结果，不影响其它检索来源。",
            code,
            message,
            data,
        )
        return []
    except BaseException as e:  # noqa: BLE001 — MCPError/UserError 等均需兜底
        code, message, data = _unwrap_mcp_error(e)
        logger.error(
            "MCP 联网搜索失败：code=%s message=%s data=%s；返回空结果，不影响其它检索来源。",
            code,
            message,
            data,
        )
        return []
