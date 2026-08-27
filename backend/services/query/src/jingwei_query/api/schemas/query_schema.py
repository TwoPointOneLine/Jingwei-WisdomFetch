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
    # 未登录访客的匿名 ID（前端本地持久化），用于把 guest 会话按「单个浏览器」
    # 隔离，避免不同未登录访客互相看到彼此的对话。登录后该字段可忽略。
    anon_id: str | None = None


class QueryResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict | None = None


class SessionRenameRequest(BaseModel):
    """重命名会话请求。"""

    title: str = Field(..., min_length=1, max_length=64)


class FeedbackRequest(BaseModel):
    """用户纠错/反馈请求（FR-COMP-05 可投诉/标识）。"""

    # 关联会话与消息（可空，支持全局反馈）
    session_id: str | None = None
    message_id: str | None = None
    # 满意度：like / dislike / none
    rating: str | None = None
    # 反馈类型：inaccurate(答案不准确) / inappropriate(内容不当) / other
    feedback_type: str | None = None
    # 反馈详情
    content: str | None = Field(default=None, max_length=2000)
    # 当前登录用户名（可选，未登录留空）
    username: str | None = None
    # 未登录访客匿名 ID（可选）
    anon_id: str | None = None
