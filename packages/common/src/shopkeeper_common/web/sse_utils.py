"""
SSE 工具：会话级事件队列与标准 SSE 打包。

为查询服务 /stream/{session_id} 提供：
- 每个 session_id 一个队列
- 把 {event, data} 推入队列
- sse_generator 持续从队列取事件并 yield SSE 事件（dict 格式，由 sse_starlette 打包）
"""
import json
import queue

from starlette.requests import Request

from shopkeeper_common.constants import SSE_EVENT_CLOSE
from shopkeeper_common.logging import logger


class SSEEvent:
    """SSE 事件名常量（与 constants.SSE_* 保持一致）。"""

    READY = "ready"          # 连接建立
    PROGRESS = "progress"    # 任务节点进度
    DELTA = "delta"          # LLM 流式输出增量
    FINAL = "final"          # 最终完整答案
    ERROR = "error"          # 错误信息
    CLOSE = "__close__"      # 关闭连接信号


_session_stream: dict[str, "queue.Queue"] = {}


def create_sse_queue(session_id: str) -> "queue.Queue":
    """获取（必要时创建）session 的 SSE 队列。

    若队列已存在则复用，避免重复调用清空已入队的事件（如 chat_query 预建
    队列、chat_stream 建立连接时都可能调用）。
    """
    existing = _session_stream.get(session_id)
    if existing is not None:
        return existing
    q: queue.Queue = queue.Queue()
    _session_stream[session_id] = q
    return q


def get_sse_queue(session_id: str) -> "queue.Queue | None":
    return _session_stream.get(session_id)


def push_to_session(session_id: str, event: str, data: dict):
    """往 session_id 对应的队列推一条事件。"""
    stream_queue = get_sse_queue(session_id)
    if stream_queue is not None:
        stream_queue.put({"event": event, "data": data})


def _sse_pack(event: str, data: dict) -> dict:
    """打包为 sse_starlette 期望的 dict 格式（event + data 字符串）。

    注意：sse_starlette 对 data 是 dict 时会以 Python repr 输出（非合法 JSON），
    为保证前端 JSON.parse 成功，我们自己把 data 序列化为 JSON 字符串。
    """
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


async def sse_generator(session_id: str, request: Request):
    """从队列持续取出事件并推送，直到收到 CLOSE。"""
    yield _sse_pack(SSEEvent.READY, {})
    queue_obj = get_sse_queue(session_id)
    if queue_obj is None:
        return
    try:
        while True:
            # 检测客户端断开
            if await request.is_disconnected():
                logger.info(f"[{session_id}] SSE 客户端断开")
                break
            try:
                item = queue_obj.get(timeout=30)
            except queue.Empty:
                yield _sse_pack(SSEEvent.PROGRESS, {"status": "processing"})
                continue
            if item is None or item.get("event") == SSE_EVENT_CLOSE:
                break
            yield _sse_pack(item["event"], item["data"])
    except Exception as e:
        logger.error(f"[{session_id}] SSE 生成异常: {e}")
        yield _sse_pack(SSEEvent.ERROR, {"error": str(e)})
    finally:
        _session_stream.pop(session_id, None)


__all__ = [
    "SSEEvent",
    "create_sse_queue",
    "get_sse_queue",
    "push_to_session",
    "sse_generator",
]
