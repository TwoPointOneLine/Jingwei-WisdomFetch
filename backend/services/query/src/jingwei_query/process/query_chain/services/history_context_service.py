"""多轮对话上下文服务（FR-QA-07 / G-03）。

节点实现：从 Mongo 读取历史并写入 state，供检索与作答共用。
历史文本渲染逻辑（build_history_text）统一放在 rag/query/history_context.py，
避免从 query_chain 主图反向导入造成的循环依赖。
"""
from __future__ import annotations

from jingwei_common.logging import logger
from jingwei_query.infra.persistence.history_repository import history_repo
from jingwei_query.rag.query.history_context import build_history_text


def load_history(state) -> dict:
    """查询链节点实现：读取历史并写入 state.history 与 state.history_text。"""
    session_id = state.get("session_id", "")
    history: list = []
    if session_id:
        try:
            # 取比注入窗口更大的上限，由 build_history_text 再裁剪，避免重复查询
            raw = history_repo.get_history(session_id, limit=20) or []
            history = [m for m in raw if m.get("role") in ("user", "assistant")]
        except Exception as e:
            logger.warning(f"读取对话历史失败，本次按无历史处理: {e}")
            history = []

    return {
        "history": history,
        "history_text": build_history_text(history, state.get("history_turns", 4)),
    }


__all__ = ["build_history_text", "load_history"]
