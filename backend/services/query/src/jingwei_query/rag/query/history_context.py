"""多轮对话历史文本渲染（FR-QA-07 / G-03）。

放在 rag/query 层（无 LangGraph 依赖），供 answer_service / query_rewrite_service
直接导入，避免从 query_chain（会触发主图编译）反向导入造成的循环依赖。
节点实现 load_history 仍位于 process/query_chain/services/history_context_service.py，
并复用本模块的 build_history_text。
"""
from __future__ import annotations

# 单条消息最大字符数（超出截断，避免历史挤占检索资料窗口）
_MAX_MSG_CHARS = 800
# 历史文本总长度上限
_MAX_TOTAL_CHARS = 3000


def _trim(text: str, limit: int = _MAX_MSG_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…（已截断）"


def build_history_text(history: list, turns: int) -> str:
    """把历史消息列表渲染为「用户：/助手：」交替文本。

    Args:
        history: [{"role": "user"|"assistant", "content": str}, ...]，按时间正序
        turns: 保留的轮数（1 轮 = 1 条 user + 1 条 assistant）

    Returns:
        渲染后的文本；无历史时返回 "（无历史对话）"
    """
    if not history:
        return "（无历史对话）"

    # 只取最近 turns 轮 => 最多 turns*2 条
    keep = max(0, int(turns)) * 2
    recent = history[-keep:] if keep else []

    lines: list[str] = []
    for m in recent:
        role = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{role}：{_trim(m.get('content', ''))}")
    if not lines:
        return "（无历史对话）"

    text = "\n".join(lines)
    if len(text) > _MAX_TOTAL_CHARS:
        # 从头部丢弃较早内容，保留最近的对话
        text = "…（更早内容已省略）\n" + text[-_MAX_TOTAL_CHARS:]
    return text


__all__ = ["build_history_text", "_trim"]
