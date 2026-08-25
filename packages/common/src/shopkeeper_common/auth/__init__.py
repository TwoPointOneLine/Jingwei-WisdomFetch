"""认证与授权共享能力（服务间鉴权）。

- AuthClient.validate_token：本地校验 token（读 MongoDB auth_tokens 集合）
- AuthClient.require_user：解析 Authorization 头，未认证抛 401
- AuthClient.get_user_role / require_role：角色与授权判断（读 user_profiles 集合）
- ROLE_PERMISSIONS：MVP 角色→权限映射（亦见 shopkeeper_common.constants）

约定：业务服务（query / user / knowledge 等）直接依赖本模块本地校验 token，
无需 HTTP 调用 auth 服务（见架构文档 4.1 服务间鉴权）。
"""
from shopkeeper_common.auth.authz import (
    ROLE_PERMISSIONS,
    auth_client,
    get_permissions,
    get_user_role,
    require_role,
    require_user,
    validate_token,
)

__all__ = [
    "ROLE_PERMISSIONS",
    "auth_client",
    "get_permissions",
    "get_user_role",
    "require_role",
    "require_user",
    "validate_token",
]
