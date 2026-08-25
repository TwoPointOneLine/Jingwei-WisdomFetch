"""Web 基础能力：SSE 流式、任务状态追踪、统一响应、异常体系。"""
from shopkeeper_common.web.errors import (
    ApiError,
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)
from shopkeeper_common.web.response import ApiResponse, fail, ok
from shopkeeper_common.web.sse_utils import (
    SSEEvent,
    create_sse_queue,
    get_sse_queue,
    push_to_session,
    sse_generator,
)
from shopkeeper_common.web.task_utils import (
    add_done_task,
    add_running_task,
    get_done_task_list,
    get_running_task_list,
    get_task_full_result,
    get_task_result,
    get_task_status,
    reset_task,
    set_task_result,
    task_push_queue,
    update_task_status,
)

__all__ = [
    "ApiError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ServiceError",
    "ApiResponse",
    "ok",
    "fail",
    "SSEEvent",
    "create_sse_queue",
    "get_sse_queue",
    "push_to_session",
    "sse_generator",
    "update_task_status",
    "get_task_status",
    "add_running_task",
    "add_done_task",
    "get_done_task_list",
    "get_running_task_list",
    "reset_task",
    "set_task_result",
    "get_task_full_result",
    "get_task_result",
    "task_push_queue",
]
