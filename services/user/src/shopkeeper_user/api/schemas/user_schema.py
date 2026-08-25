"""
用户服务数据模型：档案 / 角色 / 权限。
"""
from pydantic import BaseModel, Field
from shopkeeper_common.constants import ROLE_ADMIN, ROLE_GUEST, ROLE_MEMBER

VALID_ROLES = (ROLE_ADMIN, ROLE_MEMBER, ROLE_GUEST)
ROLE_VALUES = ",".join(VALID_ROLES)


class UserProfileCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    nickname: str | None = None
    organization: str | None = None
    role: str | None = Field(default=None, description=f"仅管理员可指定，可选：{ROLE_VALUES}")


class UserProfileUpdate(BaseModel):
    nickname: str | None = None
    organization: str | None = None
    preferences: dict | None = None


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=32)


class UserProfileResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict | None = None


class UserRoleListResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict | None = None
