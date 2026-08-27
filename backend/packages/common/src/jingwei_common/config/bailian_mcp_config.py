"""
联网搜索 MCP（DashScope WebSearch）配置。

对应 .env 中 MCP_DASHSCOPE_BASE_URL 字段。
文件名保留文档约定的 bailian_mcp_config，对外导出类名为 mcp_config。
"""
from jingwei_common.config.common import env_str


class MCPConfig:
    # DashScope WebSearch MCP 服务地址
    mcp_base_url: str = env_str(
        "MCP_DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp",
    )


mcp_config = MCPConfig()
