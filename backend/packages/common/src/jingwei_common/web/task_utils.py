"""
任务状态追踪工具（内存版）。

记录每个 task 的全局状态与节点级进度（done_list / running_list），
供服务 /status 接口轮询展示 LangGraph 执行进度。
注意：内存存储，服务重启即清空；生产可替换为 Redis/Mongo（预留仓储接口）。
"""

from jingwei_common.constants import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
)

# 全局状态存储
_TASK_STATUS: dict[str, str] = {}
_TASK_DONE: dict[str, list[str]] = {}
_TASK_RUNNING: dict[str, list[str]] = {}
_TASK_RESULT: dict[str, dict] = {}
_TASK_ERROR: dict[str, str] = {}


def update_task_status(task_id: str, status: str):
    _TASK_STATUS[task_id] = status


def set_task_error(task_id: str, error: str):
    """记录任务失败原因（FR-IMP-04），供 /status 结构化返回。"""
    _TASK_ERROR[task_id] = error


def get_task_error(task_id: str) -> str | None:
    return _TASK_ERROR.get(task_id)


def get_task_status(task_id: str) -> str | None:
    return _TASK_STATUS.get(task_id)


def add_running_task(task_id: str, node_name: str):
    lst = _TASK_RUNNING.setdefault(task_id, [])
    if node_name not in lst:
        lst.append(node_name)


def add_done_task(task_id: str, node_name: str):
    done = _TASK_DONE.setdefault(task_id, [])
    if node_name not in done:
        done.append(node_name)
    # 从 running 移除
    running = _TASK_RUNNING.get(task_id, [])
    if node_name in running:
        running.remove(node_name)


def get_done_task_list(task_id: str) -> list[str]:
    return _TASK_DONE.get(task_id, [])


def get_running_task_list(task_id: str) -> list[str]:
    return _TASK_RUNNING.get(task_id, [])


def reset_task(task_id: str):
    _TASK_STATUS.pop(task_id, None)
    _TASK_DONE.pop(task_id, None)
    _TASK_RUNNING.pop(task_id, None)
    _TASK_RESULT.pop(task_id, None)
    _TASK_ERROR.pop(task_id, None)


def set_task_result(task_id: str, result: dict):
    """保存任务的最终结果（如 llm_output / title 等），供 /task/result 兜底返回。"""
    _TASK_RESULT[task_id] = result


def get_task_full_result(task_id: str) -> dict | None:
    return _TASK_RESULT.get(task_id)


# ---------------------- 兼容文档调用别名 ----------------------
def clear_task(task_id: str):
    """清空任务状态（reset_task 别名）。"""
    reset_task(task_id)


def get_task_result(task_id: str):
    """返回任务最终结果（默认返回 done_list 摘要 + 完整结果如有）。"""
    result = {
        "status": get_task_status(task_id),
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id),
        "error": get_task_error(task_id),
    }
    full = get_task_full_result(task_id)
    if full:
        result.update(full)
    return result


def task_push_queue(task_id: str, event: str, data: dict):
    """往任务对应 SSE 队列推送事件。"""
    from jingwei_common.web.sse_utils import push_to_session

    push_to_session(task_id, event, data)


__all__ = [
    "update_task_status",
    "get_task_status",
    "add_running_task",
    "add_done_task",
    "get_done_task_list",
    "get_running_task_list",
    "reset_task",
    "clear_task",
    "set_task_result",
    "get_task_full_result",
    "get_task_result",
    "task_push_queue",
    # 任务状态常量（re-export 兼容）
    "TASK_STATUS_PENDING",
    "TASK_STATUS_PROCESSING",
    "TASK_STATUS_COMPLETED",
    "TASK_STATUS_FAILED",
]
