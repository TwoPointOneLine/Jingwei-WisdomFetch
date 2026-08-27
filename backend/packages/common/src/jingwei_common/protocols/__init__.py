"""服务间共享契约。

- 统一响应结构：`{code, message, data}`（成功 code=0）
- 错误码：constants.CODE_*
- 异常：web.errors 中定义的 ApiError 家族

服务模块之间及与网关的接口一律遵循本契约。
"""
from jingwei_common.constants import (
    CODE_BAD_REQUEST,
    CODE_FORBIDDEN,
    CODE_NOT_FOUND,
    CODE_OK,
    CODE_SERVER_ERROR,
    CODE_UNAUTHORIZED,
)
from jingwei_common.web.errors import (
    ApiError,
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)
from jingwei_common.web.response import ApiResponse, fail, ok

__all__ = [
    "CODE_OK",
    "CODE_BAD_REQUEST",
    "CODE_UNAUTHORIZED",
    "CODE_FORBIDDEN",
    "CODE_NOT_FOUND",
    "CODE_SERVER_ERROR",
    "ApiResponse",
    "ok",
    "fail",
    "ApiError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ServiceError",
]
