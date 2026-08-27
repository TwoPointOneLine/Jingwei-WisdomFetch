"""
认证服务数据模型。
"""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict | None = None
