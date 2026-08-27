"""
用户档案与角色管理（infra 层）。

数据存储：MongoDB `user_profiles` 集合（username 唯一）。
角色：admin / member / guest（见 jingwei_common.constants）。
"""
from datetime import UTC, datetime

from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.constants import (
    ALL_ROLES,
    COLLECTION_USER_PROFILES,
    ROLE_MEMBER,
)
from jingwei_common.logging import logger
from jingwei_common.web.errors import BadRequestError, NotFoundError

PROFILES_COL = COLLECTION_USER_PROFILES


def get_profile(username: str) -> dict:
    """读取用户档案。"""
    col = mongo_client.get_collection(PROFILES_COL)
    doc = col.find_one({"username": username})
    if not doc:
        raise NotFoundError("用户档案不存在")
    return _clean(doc)


def get_or_create_profile(
    username: str, *, nickname: str | None = None, role: str | None = None
) -> dict:
    """创建档案；已存在则返回现有档案（不改角色）。"""
    col = mongo_client.get_collection(PROFILES_COL)
    if existing := col.find_one({"username": username}):
        return _clean(existing)
    now = datetime.now(UTC)
    doc = {
        "username": username,
        "nickname": nickname or username,
        "role": role if role in ALL_ROLES else ROLE_MEMBER,
        "organization": "",
        "team_id": "",  # 团队空间隔离：归属团队；空表示未加入任何团队
        "preferences": {},
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    logger.info(f"创建用户档案: {username}（角色 {doc['role']}）")
    return _clean(doc)


def update_profile(username: str, data: dict) -> dict:
    """更新档案（仅非 None 字段）。"""
    col = mongo_client.get_collection(PROFILES_COL)
    if not col.find_one({"username": username}):
        raise NotFoundError("用户档案不存在")
    update = {k: v for k, v in data.items() if v is not None}
    if not update:
        return get_profile(username)
    update["updated_at"] = datetime.now(UTC)
    col.update_one({"username": username}, {"$set": update})
    return get_profile(username)


def set_role(username: str, role: str) -> dict:
    """设置用户角色（仅管理员可调用）。"""
    if role not in ALL_ROLES:
        raise BadRequestError(f"非法角色: {role}，可选 {ALL_ROLES}")
    col = mongo_client.get_collection(PROFILES_COL)
    if not col.find_one({"username": username}):
        raise NotFoundError("用户档案不存在")
    col.update_one(
        {"username": username},
        {"$set": {"role": role, "updated_at": datetime.now(UTC)}},
    )
    logger.info(f"更新角色: {username} -> {role}")
    return get_profile(username)


def set_team(username: str, team_id: str) -> dict:
    """设置用户所属团队（仅管理员可调用）。team_id 空字符串表示移出团队。"""
    col = mongo_client.get_collection(PROFILES_COL)
    if not col.find_one({"username": username}):
        raise NotFoundError("用户档案不存在")
    col.update_one(
        {"username": username},
        {"$set": {"team_id": team_id or "", "updated_at": datetime.now(UTC)}},
    )
    logger.info(f"更新团队: {username} -> team_id={team_id or ''}")
    return get_profile(username)


def get_team_id(username: str) -> str:
    """读取用户所属团队 ID（无则返回空串）。"""
    doc = mongo_client.get_collection(PROFILES_COL).find_one({"username": username})
    return (doc or {}).get("team_id", "") or ""


def _clean(doc: dict) -> dict:
    """去掉 _id，时间转 ISO 字符串，便于 JSON 序列化。"""
    out = {k: v for k, v in doc.items() if k != "_id"}
    for key in ("created_at", "updated_at"):
        value = out.get(key)
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out
