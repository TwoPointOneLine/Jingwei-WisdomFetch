"""
查询链全局状态定义（TypedDict）。

字段含：输入/输出、重新措辞结果、多路召回（向量/HyDE/联网）、RRF 融合、重排结果、
LLM 答案、流式增量队列。

并行安全：
查询链存在三路并行召回（vector/hyde/mcp）与 fan-in 融合节点（rrf/rerank），
这些节点都会返回各自对应的 list 字段。为避免 LangGraph 报
"Can receive only one value per step"，对会被并发写入的 list 字段统一加
"后写覆盖" reducer（Annotated[T, _last_write_wins]）。
"""
from typing import Annotated, TypedDict

from langgraph.graph import add_messages  # noqa: F401  (占位，保持 LangGraph 风格约定)


def _last_write_wins(a, b):
    """reducer：并发/多次写入时以后一次写入为准（b 非 None 则取 b）。"""
    return b if b is not None else a


class QueryGraphState(TypedDict):
    task_id: str
    session_id: str
    username: str
    query: str
    user_query: str
    item_name: str
    model: str
    rephrased_query: str
    # ── 多轮上下文（FR-QA-07 / G-03）──────────────────────────
    # history：原始消息列表；history_text：裁剪后可直接注入 prompt 的文本
    # history_turns：注入作答 prompt 的轮数（由 rag_config 传入）
    history: Annotated[list, _last_write_wins]
    history_text: Annotated[str, _last_write_wins]
    history_turns: int
    keywords: Annotated[list, _last_write_wins]
    vector_documents: Annotated[list, _last_write_wins]
    hyde_documents: Annotated[list, _last_write_wins]
    web_documents: Annotated[list, _last_write_wins]
    rrf_documents: Annotated[list, _last_write_wins]
    rerank_documents: Annotated[list, _last_write_wins]
    llm_output: Annotated[str, _last_write_wins]
    delta_queue: object
    need_stream_output: bool


__all__ = ["QueryGraphState"]
