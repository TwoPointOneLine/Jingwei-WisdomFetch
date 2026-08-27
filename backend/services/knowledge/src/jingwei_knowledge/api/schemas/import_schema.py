"""
导入服务数据模型。
"""
from pydantic import BaseModel


class UploadResponse(BaseModel):
    code: int = 200
    message: str
    task_ids: list[str]


class ImportStatusResponse(BaseModel):
    code: int = 200
    task_id: str
    status: str | None = None
    done_list: list[str]
    running_list: list[str]
    error: str | None = None  # FR-IMP-04：失败原因（结构化返回）
