"""
认证服务 HTTP 入口：注册、登录、校验 token、注销。

用户数据存 MongoDB（users / auth_tokens / user_profiles 集合），
密码 PBKDF2 加盐哈希，token 用 secrets 生成。无第三方 JWT/密码依赖。
"""
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from jingwei_common.auth import get_user_role
from jingwei_common.config import settings
from starlette.responses import JSONResponse

from jingwei_auth.api.schemas.auth_schema import AuthResponse, LoginRequest, RegisterRequest
from jingwei_auth.infra.auth.auth_service import (
    issue_token,
    register,
    revoke_token,
    validate_token,
    verify_password,
)

app = FastAPI(
    title=settings.auth_app_name,
    description="精卫 认证服务：注册、登录、鉴权。",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins.split(",")) if settings.cors_origins != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resp(code: int, message: str, data: dict | None = None) -> AuthResponse:
    return AuthResponse(code=code, message=message, data=data)


@app.post("/auth/register", response_model=AuthResponse)
async def register_endpoint(req: RegisterRequest):
    """注册新用户（同步初始化用户档案与默认角色）。"""
    try:
        user = register(req.username, req.password)
        return _resp(200, "注册成功", user)
    except ValueError as e:
        return _resp(400, str(e))


@app.post("/auth/login", response_model=AuthResponse)
async def login_endpoint(req: LoginRequest):
    """登录，返回 token 与用户名。"""
    if not verify_password(req.username, req.password):
        return _resp(401, "用户名或密码错误")
    token = issue_token(req.username)
    return _resp(
        200,
        "登录成功",
        {"username": req.username, "token": token},
    )


@app.get("/auth/me", response_model=AuthResponse)
async def me(authorization: str | None = Header(default=None)):
    """校验 token，返回当前用户及其角色。"""
    token = _extract_token(authorization)
    username = validate_token(token) if token else None
    if not username:
        return _resp(401, "未登录或登录已过期")
    return _resp(200, "ok", {"username": username, "role": get_user_role(username)})


@app.post("/auth/logout", response_model=AuthResponse)
async def logout(authorization: str | None = Header(default=None)):
    """注销当前 token。"""
    token = _extract_token(authorization)
    if token:
        revoke_token(token)
    return _resp(200, "已注销")


def _extract_token(authorization: str | None) -> str:
    """从 Authorization 头提取 token（支持 Bearer 前缀）。"""
    if not authorization:
        return ""
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


@app.get("/health")
async def health():
    """健康检查。"""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.auth_app_port)
