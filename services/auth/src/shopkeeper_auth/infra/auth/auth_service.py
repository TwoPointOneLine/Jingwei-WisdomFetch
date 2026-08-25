"""
认证服务：用户注册、登录、token 管理（标准库实现，无第三方依赖）。

- 密码哈希：PBKDF2-HMAC-SHA256 + 随机盐（hashlib/secrets 标准库）。
- token：secrets.token_hex，存储于 MongoDB `auth_tokens` 集合。
- 用户：存 MongoDB `users` 集合。
- 注册时同步初始化 `user_profiles` 档案（角色默认 member；命中
  AUTH_BOOTSTRAP_ADMIN 环境变量的用户为 admin）。
"""
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime

from shopkeeper_common.clients.mongo_client import mongo_client
from shopkeeper_common.constants import COLLECTION_USER_PROFILES, ROLE_ADMIN, ROLE_MEMBER
from shopkeeper_common.logging import logger

_ITERATIONS = 120_000
_TOKEN_TTL_DAYS = 7

USERS_COL = "users"
TOKENS_COL = "auth_tokens"


def _hash_password(password: str, salt: str) -> str:
    """PBKDF2-HMAC-SHA256 哈希。"""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    ).hex()


def _default_role(username: str) -> str:
    """注册默认角色：命中 AUTH_BOOTSTRAP_ADMIN（逗号分隔）则为 admin，否则 member。"""
    bootstrap = os.environ.get("AUTH_BOOTSTRAP_ADMIN", "")
    admins = {u.strip() for u in bootstrap.split(",") if u.strip()}
    return ROLE_ADMIN if username in admins else ROLE_MEMBER


def register(username: str, password: str) -> dict:
    """注册新用户，并同步初始化用户档案（user_profiles）。"""
    users = mongo_client.get_collection(USERS_COL)
    username = username.strip()
    if users.find_one({"username": username}):
        raise ValueError("用户名已存在")
    salt = secrets.token_hex(16)
    users.insert_one(
        {
            "username": username,
            "salt": salt,
            "password_hash": _hash_password(password, salt),
            "created_at": datetime.now(UTC),
        }
    )
    role = _default_role(username)
    profiles = mongo_client.get_collection(COLLECTION_USER_PROFILES)
    profiles.insert_one(
        {
            "username": username,
            "nickname": username,
            "role": role,
            "organization": "",
            "preferences": {},
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )
    logger.info(f"新用户注册: {username}（角色 {role}）")
    return {"username": username, "role": role}


def verify_password(username: str, password: str) -> bool:
    """校验用户名密码。"""
    users = mongo_client.get_collection(USERS_COL)
    doc = users.find_one({"username": username})
    if not doc:
        return False
    expected = _hash_password(password, doc["salt"])
    return hmac.compare_digest(expected, doc["password_hash"])


def issue_token(username: str) -> str:
    """签发 token 并存储。"""
    token = secrets.token_hex(32)
    tokens = mongo_client.get_collection(TOKENS_COL)
    tokens.insert_one(
        {
            "token": token,
            "username": username,
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC).isoformat(),
        }
    )
    return token


def validate_token(token: str) -> str | None:
    """校验 token，返回对应用户名；无效返回 None。"""
    if not token:
        return None
    tokens = mongo_client.get_collection(TOKENS_COL)
    doc = tokens.find_one({"token": token})
    if not doc:
        return None
    return doc.get("username")


def revoke_token(token: str):
    """注销 token。"""
    tokens = mongo_client.get_collection(TOKENS_COL)
    tokens.delete_many({"token": token})
