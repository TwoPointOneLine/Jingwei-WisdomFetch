"""
历史对话出口（infra 层）。

业务/节点层统一通过 history_repo 读写多轮对话上下文。
"""
from shopkeeper_common.clients.mongo_history_utils import (
    append_message,
    clear_session,
    create_session_if_not_exists,
    get_history,
    list_sessions,
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

    def list_sessions(self, username: str | None = None, limit: int = 100) -> list[dict]:
        return list_sessions(username, limit=limit)

    def rename_session(self, session_id: str, title: str):
        return rename_session(session_id, title)


history_repo = HistoryRepository()
