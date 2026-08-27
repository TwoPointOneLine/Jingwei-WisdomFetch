"""
历史对话出口（infra 层）。

业务/节点层统一通过 history_repo 读写多轮对话上下文。
"""
from jingwei_common.clients.mongo_history_utils import (
    append_message,
    claim_guest_sessions,
    clear_session,
    create_session_if_not_exists,
    get_history,
    get_session_meta,
    list_sessions,
    reassign_session,
    rename_session,
    update_session_meta,
)


class HistoryRepository:
    def create_session_if_not_exists(self, session_id: str, meta: dict | None = None):
        return create_session_if_not_exists(session_id, meta)

    def append_message(self, session_id: str, role: str, content: str):
        return append_message(session_id, role, content)

    def get_history(self, session_id: str, limit: int = 10) -> list[dict]:
        return get_history(session_id, limit=limit)

    def clear_session(self, session_id: str):
        return clear_session(session_id)

    def update_session_meta(self, session_id: str, meta: dict):
        return update_session_meta(session_id, meta)

    def list_sessions(self, username: str | None = None, anon_id: str | None = None, limit: int = 100) -> list[dict]:
        return list_sessions(username, anon_id=anon_id, limit=limit)

    def rename_session(self, session_id: str, title: str):
        return rename_session(session_id, title)

    def reassign_session(self, session_id: str, username: str):
        """将会话从 guest 归并到登录用户（保留历史）。"""
        return reassign_session(session_id, username)

    def claim_guest_sessions(self, anon_id: str, username: str) -> int:
        """登录时批量归并本浏览器 guest 会话到当前用户，返回归并数量。"""
        return claim_guest_sessions(anon_id, username)

    def get_session_meta(self, session_id: str) -> dict:
        """读取会话 meta（用于归属校验）。"""
        return get_session_meta(session_id)


history_repo = HistoryRepository()
