"""统一异常体系。

业务代码抛出对应异常，上层（服务路由/网关）捕获后映射为统一响应
`{"code", "message", "data"}` 与 HTTP 状态码。
"""
from shopkeeper_common.constants import (
    CODE_BAD_REQUEST,
    CODE_FORBIDDEN,
    CODE_NOT_FOUND,
    CODE_SERVER_ERROR,
    CODE_UNAUTHORIZED,
)


class ApiError(Exception):
    """业务异常基类。"""

    code: int = CODE_SERVER_ERROR
    http_status: int = 500
    message: str = "服务内部错误"

    def __init__(self, message: str | None = None, *, code: int | None = None):
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "data": None}


class BadRequestError(ApiError):
    """参数错误（400）。"""

    code = CODE_BAD_REQUEST
    http_status = 400
    message = "请求参数错误"


class UnauthorizedError(ApiError):
    """未认证（401）。"""

    code = CODE_UNAUTHORIZED
    http_status = 401
    message = "未认证或登录已过期"


class ForbiddenError(ApiError):
    """无权限（403）。"""

    code = CODE_FORBIDDEN
    http_status = 403
    message = "无权限访问"


class NotFoundError(ApiError):
    """资源不存在（404）。"""

    code = CODE_NOT_FOUND
    http_status = 404
    message = "资源不存在"


class ServiceError(ApiError):
    """服务内部错误（500）。"""

    code = CODE_SERVER_ERROR
    http_status = 500
    message = "服务内部错误"


__all__ = [
    "ApiError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ServiceError",
]
