"""网关统一入口（端口 8080）。

职责（12 号文档 4.3）：
- 路由转发：`/api/auth|user|knowledge|import|query/*` → 各后端服务
- 统一鉴权前置（strict / optional 两档，SSE 免鉴权）
- CORS / 限流 / 访问日志
- SSE 流式代理
- 静态资源托管（frontend/dist）
"""
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from shopkeeper_common.auth import auth_client
from shopkeeper_common.web.errors import ApiError

from .config import AUTH_MODE, RATE_LIMIT, build_routes
from .middleware import GatewayAuth, RateLimiter, log_access
from .proxy import GatewayProxy

app = FastAPI(
    title="掌柜智库网关",
    version="0.1.0",
    docs_url="/gateway/docs",
    openapi_url="/gateway/openapi.json",
)

# CORS：网关为前端统一入口，开发阶段全开
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

proxy = GatewayProxy(routes=build_routes())
gateway_auth = GatewayAuth(auth_client=auth_client, mode=AUTH_MODE)
rate_limiter = RateLimiter(limit=RATE_LIMIT)


@app.middleware("http")
async def gateway_dispatch(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except ApiError as exc:
        response = JSONResponse(status_code=exc.http_status, content=exc.to_dict())
    except Exception:  # noqa: BLE001
        logger.exception("[gateway] 未捕获异常")
        response = JSONResponse(
            status_code=500,
            content={"code": 500, "message": "网关内部错误", "data": None},
        )
    duration_ms = (time.perf_counter() - start) * 1000
    client_host = request.client.host if request.client else ""
    log_access(request.method, request.url.path, response.status_code, duration_ms, client_host)
    return response


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def gateway_proxy(path: str, request: Request):
    # 统一鉴权前置
    gateway_auth.check(request)
    # 限流（SSE 长连接不计入）
    if not gateway_auth.is_sse(request.url.path):
        client_key = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(client_key):
            return JSONResponse(
                status_code=429,
                content={"code": 429, "message": "请求过于频繁，请稍后再试", "data": None},
            )
    return await proxy.forward(request)


@app.get("/health")
async def health():
    """健康检查：返回网关状态与后端路由表。"""
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "status": "up",
            "gateway": "shopkeeper-gateway",
            "backends": {prefix: url for prefix, url in proxy.routes.items()},
        },
    }


# ── 静态资源托管（frontend/dist，存在时挂载）──────────────────────
def _find_dist() -> str | None:
    env_dir = os.getenv("GATEWAY_DIST_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "frontend" / "dist"
        if candidate.is_dir():
            return str(candidate)
    return None


DIST_DIR = _find_dist()
if DIST_DIR:
    _assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def index():
        index_file = os.path.join(DIST_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return JSONResponse({"code": 404, "message": "前端未构建", "data": None})
