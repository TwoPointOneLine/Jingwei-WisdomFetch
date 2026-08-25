"""统一响应模型。

所有服务接口返回 `{"code": int, "message": str, "data": object|null}`，
成功时 code=0，失败时 code 为错误码（见 constants.CODE_*）。
HTTP 状态码由上层根据 code 映射。
"""
from typing import Any

from shopkeeper_common.constants import CODE_OK


def ok(data: Any = None, message: str = "ok") -> dict:
    """成功响应。"""
    return {"code": CODE_OK, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    """失败响应。"""
    return {"code": code, "message": message, "data": data}


class ApiResponse:
    """统一响应构造器（面向对象风格，兼容 ok/fail 函数）。"""

    @staticmethod
    def ok(data: Any = None, message: str = "ok") -> dict:
        return ok(data, message)

    @staticmethod
    def fail(code: int, message: str, data: Any = None) -> dict:
        return fail(code, message, data)


__all__ = ["ApiResponse", "ok", "fail"]
