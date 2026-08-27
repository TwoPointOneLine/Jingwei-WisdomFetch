"""
历史对话 MongoDB 工具。

存储会话(session)与消息(message)，供查询链多轮对话上下文使用。
复用 jingwei_common.clients.mongo_client 的连接。
"""
from datetime import datetime
from typing import Any

from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.constants import (
    COLLECTION_MESSAGES,
    COLLECTION_SESSIONS,
)

SESSION_COLLECTION = COLLECTION_SESSIONS
MESSAGE_COLLECTION = COLLECTION_MESSAGES


def create_session_if_not_exists(session_id: str, meta: dict | None = None):
    col = mongo_client.get_collection(SESSION_COLLECTION)
    if col.find_one({"session_id": session_id}):
        return
    doc = {
        "session_id": session_id,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "meta": meta or {},
    }
    col.insert_one(doc)


def append_message(session_id: str, role: str, content: str):
    col = mongo_client.get_collection(MESSAGE_COLLECTION)
    col.insert_one(
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(),
        }
    )


def get_history(session_id: str, limit: int = 10) -> list[dict]:
    """返回该会话的最近 limit 条消息（按时间升序）。"""
    col = mongo_client.get_collection(MESSAGE_COLLECTION)
    cursor = col.find({"session_id": session_id}).sort("created_at", 1).limit(limit)
    return [
        {"role": m.get("role"), "content": m.get("content")}
        for m in cursor
    ]


def clear_session(session_id: str):
    mongo_client.get_collection(SESSION_COLLECTION).delete_many({"session_id": session_id})
    mongo_client.get_collection(MESSAGE_COLLECTION).delete_many({"session_id": session_id})


def update_session_meta(session_id: str, meta: dict):
    mongo_client.get_collection(SESSION_COLLECTION).update_one(
        {"session_id": session_id}, {"$set": {"meta": meta, "updated_at": datetime.now()}}
    )


def list_sessions(username: str | None = None, limit: int = 100) -> list[dict]:
    """返回会话列表（按更新时间倒序）。

    若提供 username，仅返回该用户创建的会话（meta.username 匹配）；
    否则返回全部。每条含 session_id / title / meta / updated_at。
    """
    query: dict[str, Any] = {}
    if username:
        query["meta.username"] = username
    col = mongo_client.get_collection(SESSION_COLLECTION)
    cursor = col.find(query).sort("updated_at", -1).limit(limit)
    sessions = []
    for s in cursor:
        meta = s.get("meta") or {}
        sessions.append(
            {
                "session_id": s.get("session_id"),
                "title": meta.get("title") or meta.get("topic") or "",
                "updated_at": s.get("updated_at"),
                "meta": meta,
            }
        )
    return sessions


def rename_session(session_id: str, title: str):
    """重命名会话标题（写入 meta.title）。"""
    col = mongo_client.get_collection(SESSION_COLLECTION)
    col.update_one(
        {"session_id": session_id},
        {"$set": {"meta.title": title, "updated_at": datetime.now()}},
    )


def get_session_meta(session_id: str) -> dict:
    """读取会话 meta（用于归属校验），不存在返回空 dict。"""
    col = mongo_client.get_collection(SESSION_COLLECTION)
    s = col.find_one({"session_id": session_id})
    return (s.get("meta") or {}) if s else {}


def reassign_session(session_id: str, username: str):
    """将会话从 guest 归并到登录用户（保留历史），更新 meta.username。"""
    col = mongo_client.get_collection(SESSION_COLLECTION)
    col.update_one(
        {"session_id": session_id},
        {"$set": {"meta.username": username, "updated_at": datetime.now()}},
    )


def claim_guest_sessions(anon_id: str, username: str) -> int:
    """登录时批量归并本浏览器(anon_id)下 guest 会话到当前用户，返回归并数量。"""
    if not anon_id:
        return 0
    col = mongo_client.get_collection(SESSION_COLLECTION)
    result = col.update_many(
        {"meta.anon_id": anon_id, "meta.username": "guest"},
        {"$set": {"meta.username": username, "updated_at": datetime.now()}},
    )
    return result.modified_count or 0


__all__ = [
    "create_session_if_not_exists",
    "append_message",
    "get_history",
    "clear_session",
    "update_session_meta",
    "list_sessions",
    "rename_session",
    "get_session_meta",
    "reassign_session",
    "claim_guest_sessions",
    "SESSION_COLLECTION",
    "MESSAGE_COLLECTION",
]
