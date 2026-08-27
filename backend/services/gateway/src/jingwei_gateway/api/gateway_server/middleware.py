"""网关中间件：统一鉴权前置 / 限流 / 访问日志。"""
import time

from jingwei_common.web.errors import UnauthorizedError
from loguru import logger
from starlette.requests import Request

from .config import PUBLIC_PATHS, SSE_PREFIX


class GatewayAuth:
    """统一鉴权前置：校验 `Authorization: Bearer <token>`。

    模式：
    - strict：白名单外必须携带有效 token，否则 401
    - optional（默认）：携带 token 必须有效；未携带放行（guest）
    白名单（注册/登录/me/登出/模型列表）始终放行；
    SSE 端点放行（EventSource 无法带 header），支持 `?token=` 兜底。
    """

    def __init__(self, auth_client, mode: str = "optional", public_paths=PUBLIC_PATHS):
        self.auth_client = auth_client
        self.mode = mode
        self.public_paths = public_paths

    def is_public(self, path: str, method: str) -> bool:
        if method == "OPTIONS":
            return True
        return any(path == p or path.startswith(p + "/") for p in self.public_paths)

    def is_sse(self, path: str) -> bool:
        return path == SSE_PREFIX or path.startswith(SSE_PREFIX + "/")

    def _resolve_token(self, request: Request) -> str:
        token = self.auth_client.extract_token(request.headers.get("Authorization"))
        if not token:
            token = request.query_params.get("token", "")
        return token.strip()

    def check(self, request: Request) -> None:
        """鉴权前置；不通过抛 UnauthorizedError。"""
        path = request.url.path
        if self.is_public(path, request.method):
            return
        token = self._resolve_token(request)
        if token:
            if not self.auth_client.validate_token(token):
                raise UnauthorizedError("未登录或登录已过期")
            return
        if self.is_sse(path):
            return
        if self.mode == "strict":
            raise UnauthorizedError("未登录或登录已过期")
        # optional：匿名放行（guest 角色）


class RateLimiter:
    """简单内存固定窗口限流（按 key，默认 IP）。0 表示关闭。"""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        timestamps = self._buckets.setdefault(key, [])
        cutoff = now - self.window
        timestamps[:] = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= self.limit:
            return False
        timestamps.append(now)
        return True


def log_access(method: str, path: str, status: int, duration_ms: float, client: str = "") -> None:
    """访问日志。"""
    logger.info(f"[gateway] {client} {method} {path} -> {status} ({duration_ms:.1f}ms)")
