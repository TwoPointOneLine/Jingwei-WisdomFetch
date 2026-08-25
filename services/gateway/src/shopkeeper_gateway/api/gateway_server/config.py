"""网关配置：后端路由表 / 免鉴权白名单 / SSE 前缀。

路由映射（12 号文档 4.3 网关职责）：
- `/api/auth/*` → auth 服务（8083）
- `/api/user/*` → user 服务（8084）
- `/api/knowledge/*` 与 `/api/import/*` → knowledge 服务（8081，兼容前端旧前缀）
- `/api/query/*` → query 服务（8082）
"""
import os

from shopkeeper_common.config import settings

# 后端服务间转发默认本机回环地址；跨主机/容器部署可覆盖：
# - GATEWAY_BACKEND_HOST：全部后端统一 host（默认 127.0.0.1）
# - GATEWAY_AUTH_HOST / GATEWAY_USER_HOST / GATEWAY_IMPORT_HOST / GATEWAY_QUERY_HOST：
#   各后端独立 host（Docker Compose 中填容器服务名），优先级高于统一 host
BACKEND_HOST = os.getenv("GATEWAY_BACKEND_HOST", "127.0.0.1")


def _backend_url(port: int) -> str:
    return f"http://{BACKEND_HOST}:{port}"


def _host(env_key: str) -> str:
    """取某后端独立 host 覆盖，未设置则回退统一 host。"""
    return os.getenv(env_key, "").strip() or BACKEND_HOST


def build_routes() -> dict[str, str]:
    """构建 前缀 → 后端基础 URL 映射。"""
    return {
        "/api/auth": f"http://{_host('GATEWAY_AUTH_HOST')}:{settings.auth_app_port}",
        "/api/user": f"http://{_host('GATEWAY_USER_HOST')}:{settings.user_app_port}",
        "/api/knowledge": f"http://{_host('GATEWAY_IMPORT_HOST')}:{settings.import_app_port}",
        "/api/import": f"http://{_host('GATEWAY_IMPORT_HOST')}:{settings.import_app_port}",
        "/api/query": f"http://{_host('GATEWAY_QUERY_HOST')}:{settings.query_app_port}",
    }


# 完全免鉴权：/api/auth/* 整体放行（注册/登录/me/登出由认证服务自身校验 token）；
# /api/query/models 模型列表公开。
PUBLIC_PATHS: tuple[str, ...] = (
    "/api/auth",
    "/api/query/models",
)

# SSE 端点（EventSource 无法携带 Authorization 头，允许匿名或通过 ?token= 兜底）
SSE_PREFIX = "/api/query/chat/stream"

# 鉴权模式：strict=必须 token / optional=带 token 则校验（默认）
AUTH_MODE = settings.gateway_auth_mode

# 限流：每分钟每 IP 最大请求数（0=关闭）
RATE_LIMIT = settings.gateway_rate_limit
