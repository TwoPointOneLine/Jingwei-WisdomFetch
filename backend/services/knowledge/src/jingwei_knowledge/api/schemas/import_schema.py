"""
导入服务数据模型。
"""
from pydantic import BaseModel


class RejectedFile(BaseModel):
    """G-01：被拒绝的文件（格式不支持等），随上传响应一并返回，避免静默丢弃。"""

    filename: str
    reason: str


class UploadResponse(BaseModel):
    code: int = 200
    message: str
    task_ids: list[str]
    # G-01：被拒文件清单。前端须展示，否则用户会认为"上传成功却查不到"。
    rejected: list[RejectedFile] = []


class ImportStatusResponse(BaseModel):
    code: int = 200
    task_id: str
    status: str | None = None
    done_list: list[str]
    running_list: list[str]
    error: str | None = None  # FR-IMP-04：失败原因（结构化返回）
