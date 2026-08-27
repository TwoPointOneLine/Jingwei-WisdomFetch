"""
用户服务 HTTP 入口：用户档案 / 角色 / 权限管理。

鉴权：
- 所有业务接口需携带有效 token（Authorization: Bearer <token>）。
- 角色管理（设置角色）仅 admin 可用；档案修改限本人或 admin。
"""
from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from jingwei_common.audit import audit_log
from jingwei_common.auth.authz import (
    ROLE_PERMISSIONS,
    auth_client,
    get_permissions,
    require_user,
)
from jingwei_common.config import settings
from jingwei_common.constants import ROLE_ADMIN
from jingwei_common.web.errors import ApiError, ForbiddenError
from starlette.responses import JSONResponse

from jingwei_user.api.schemas.user_schema import (
    RoleUpdateRequest,
    TeamUpdateRequest,
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
    UserRoleListResponse,
)
from jingwei_user.infra.user.user_service import (
    get_or_create_profile,
    get_profile,
    set_role,
    set_team,
    update_profile,
)

app = FastAPI(
    title=settings.user_app_name,
    description="精卫 用户服务：用户档案、角色与权限管理。",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins.split(",")) if settings.cors_origins != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ROLE_LABELS = {
    "admin": "管理员",
    "member": "普通成员",
    "guest": "访客",
}


@app.exception_handler(ApiError)
async def _api_error_handler(request: Request, exc: ApiError):
    """将业务异常映射为统一响应。"""
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


@app.post("/user/profile", response_model=UserProfileResponse)
async def create_profile(req: UserProfileCreate, authorization: str | None = Header(default=None)):
    """创建/初始化用户档案。admin 可指定角色，普通用户仅可为本人建档。"""
    caller = require_user(authorization)
    is_admin = auth_client.get_user_role(caller) == ROLE_ADMIN
    if req.role and not is_admin:
        raise ForbiddenError("仅管理员可指定角色")
    if req.username != caller and not is_admin:
        raise ForbiddenError("仅管理员可代他人建档")
    profile = get_or_create_profile(req.username, nickname=req.nickname, role=req.role)
    return UserProfileResponse(message="档案已就绪", data=profile)


@app.get("/user/profile/{username}", response_model=UserProfileResponse)
async def read_profile(username: str, authorization: str | None = Header(default=None)):
    """读取用户档案（任意已登录用户）。"""
    require_user(authorization)
    return UserProfileResponse(data=get_profile(username))


@app.patch("/user/profile/{username}", response_model=UserProfileResponse)
async def modify_profile(
    username: str, req: UserProfileUpdate, authorization: str | None = Header(default=None)
):
    """修改档案（仅本人或 admin）。"""
    caller = require_user(authorization)
    if username != caller and auth_client.get_user_role(caller) != ROLE_ADMIN:
        raise ForbiddenError("仅本人或管理员可修改档案")
    return UserProfileResponse(message="档案已更新", data=update_profile(username, req.model_dump()))


@app.get("/user/roles", response_model=UserRoleListResponse)
async def list_roles(authorization: str | None = Header(default=None)):
    """角色列表与权限说明（任意已登录用户）。"""
    require_user(authorization)
    roles = [
        {"role": role, "label": _ROLE_LABELS[role], "permissions": ROLE_PERMISSIONS.get(role, [])}
        for role in ("admin", "member", "guest")
    ]
    return UserRoleListResponse(data={"roles": roles})


@app.post("/user/{username}/role", response_model=UserProfileResponse)
async def assign_role(username: str, req: RoleUpdateRequest, authorization: str | None = Header(default=None)):
    """设置用户角色（仅 admin）。"""
    caller = require_user(authorization)
    auth_client.require_role(caller, {ROLE_ADMIN})
    result = set_role(username, req.role)
    # NFR-SEC-04：权限变更审计留痕
    audit_log(
        action="user_role_change",
        actor=caller,
        actor_role=ROLE_ADMIN,
        detail={"target_user": username, "new_role": req.role},
        source="user",
    )
    return UserProfileResponse(message="角色已更新", data=result)


@app.post("/user/{username}/team", response_model=UserProfileResponse)
async def assign_team(username: str, req: TeamUpdateRequest, authorization: str | None = Header(default=None)):
    """设置用户所属团队（仅 admin）。team_id 空字符串表示移出团队。"""
    caller = require_user(authorization)
    auth_client.require_role(caller, {ROLE_ADMIN})
    result = set_team(username, req.team_id)
    # NFR-SEC-04：权限变更审计留痕
    audit_log(
        action="user_team_change",
        actor=caller,
        actor_role=ROLE_ADMIN,
        detail={"target_user": username, "new_team_id": req.team_id},
        source="user",
    )
    return UserProfileResponse(message="团队已更新", data=result)


@app.get("/user/{username}/permissions", response_model=UserRoleListResponse)
async def user_permissions(username: str, authorization: str | None = Header(default=None)):
    """查询用户权限（任意已登录用户）。"""
    require_user(authorization)
    return UserRoleListResponse(
        data={"username": username, "role": auth_client.get_user_role(username), "permissions": get_permissions(username)}
    )


@app.get("/health")
async def health():
    """健康检查。"""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.user_app_port)
