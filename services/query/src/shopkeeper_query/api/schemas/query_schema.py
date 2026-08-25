"""
查询服务数据模型。
"""
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    session_id: str
    query: str
    need_stream_output: bool = True
    item_name: str | None = None
    # 对话模型（如 qwen-plus / qwen-vl-max），为空则用默认模型
    model: str | None = None
    # 当前登录用户名（用于会话隔离），未登录可空
    username: str | None = None


class QueryResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict | None = None


class SessionRenameRequest(BaseModel):
    """重命名会话请求。"""

    title: str = Field(..., min_length=1, max_length=64)
