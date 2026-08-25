"""Web 基础能力测试：统一响应、异常、SSE 队列、任务状态。"""
import pytest
from shopkeeper_common.web.errors import ApiError, NotFoundError, UnauthorizedError
from shopkeeper_common.web.response import fail, ok
from shopkeeper_common.web.sse_utils import create_sse_queue, get_sse_queue
from shopkeeper_common.web.task_utils import (
    add_done_task,
    add_running_task,
    get_done_task_list,
    get_running_task_list,
    get_task_result,
    get_task_status,
    reset_task,
    set_task_result,
    update_task_status,
)


def test_response_ok():
    r = ok(data={"a": 1})
    assert r["code"] == 0
    assert r["data"] == {"a": 1}
    assert r["message"] == "ok"


def test_response_fail():
    r = fail(400, "bad")
    assert r["code"] == 400
    assert r["message"] == "bad"
    assert r["data"] is None


def test_errors():
    with pytest.raises(ApiError):
        raise UnauthorizedError("登录已过期")
    err = NotFoundError()
    assert err.to_dict()["code"] == 404
    assert err.http_status == 404


def test_sse_queue():
    q = create_sse_queue("s1")
    assert get_sse_queue("s1") is q
    # 重复创建复用同一队列
    assert create_sse_queue("s1") is q


def test_task_tracker():
    update_task_status("t1", "processing")
    assert get_task_status("t1") == "processing"
    add_running_task("t1", "node_a")
    assert get_running_task_list("t1") == ["node_a"]
    add_done_task("t1", "node_a")
    assert get_running_task_list("t1") == []
    assert get_done_task_list("t1") == ["node_a"]
    set_task_result("t1", {"title": "x"})
    result = get_task_result("t1")
    assert result["status"] == "processing"
    assert result["title"] == "x"
    reset_task("t1")
    assert get_task_status("t1") is None
