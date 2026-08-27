"""认证客户端与授权工具。

供 auth / user / query / knowledge 等服务本地校验 token 与角色，
避免跨服务 HTTP 调用鉴权。存储依赖 MongoDB 共享集合：
- auth_tokens：token -> username（auth 服务签发）
- user_profiles：username -> {nickname, role, ...}（auth 注册时初始化 / user 服务维护）
"""
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.constants import (
    COLLECTION_AUTH_TOKENS,
    COLLECTION_USER_PROFILES,
    ROLE_GUEST,
    ROLE_PERMISSIONS,
)
from jingwei_common.web.errors import ForbiddenError, UnauthorizedError

TOKENS_COL = COLLECTION_AUTH_TOKENS
PROFILES_COL = COLLECTION_USER_PROFILES


class AuthClient:
    """认证客户端：token 本地校验 + 角色授权。"""

    def extract_token(self, authorization: str | None) -> str:
        """从 Authorization 头提取 token（支持 Bearer 前缀）。"""
        if not authorization:
            return ""
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return authorization.strip()

    def validate_token(self, token: str) -> str | None:
        """校验 token，返回对应用户名；无效返回 None。"""
        if not token:
            return None
        doc = mongo_client.get_collection(TOKENS_COL).find_one({"token": token})
        if not doc:
            return None
        return doc.get("username")

    def require_user(self, authorization: str | None) -> str:
        """解析并校验 token，返回用户名；未认证抛 UnauthorizedError。"""
        username = self.validate_token(self.extract_token(authorization))
        if not username:
            raise UnauthorizedError("未登录或登录已过期")
        return username

    def get_user_role(self, username: str) -> str:
        """读取用户角色；档案不存在时按 guest 处理。"""
        doc = mongo_client.get_collection(PROFILES_COL).find_one({"username": username})
        return (doc or {}).get("role") or ROLE_GUEST

    def get_user_team(self, username: str) -> str:
        """读取用户所属团队 ID；档案不存在或无团队时返回空串。"""
        doc = mongo_client.get_collection(PROFILES_COL).find_one({"username": username})
        return (doc or {}).get("team_id", "") or ""

    def require_role(self, username: str, roles: set[str]) -> str:
        """校验用户角色是否在 roles 中，否则抛 ForbiddenError。"""
        if self.get_user_role(username) not in roles:
            raise ForbiddenError("无权限执行该操作")
        return username

    def get_permissions(self, username: str) -> list[str]:
        """返回用户角色对应的权限列表。"""
        return ROLE_PERMISSIONS.get(self.get_user_role(username), [])


# 全局单例（业务代码推荐使用）
auth_client = AuthClient()

# 函数式别名（兼容）
extract_token = auth_client.extract_token
validate_token = auth_client.validate_token
require_user = auth_client.require_user
get_user_role = auth_client.get_user_role
get_user_team = auth_client.get_user_team
require_role = auth_client.require_role
get_permissions = auth_client.get_permissions


__all__ = [
    "AuthClient",
    "auth_client",
    "extract_token",
    "validate_token",
    "require_user",
    "get_user_role",
    "require_role",
    "get_permissions",
]
