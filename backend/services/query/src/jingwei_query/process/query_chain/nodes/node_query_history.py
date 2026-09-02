from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_query.process.query_chain.services.history_context_service import load_history
from jingwei_query.process.query_chain.state import QueryGraphState


@node_log("node_query_history")
def node_query_history(state: QueryGraphState) -> QueryGraphState:
    """读取多轮对话历史，供后续改写与作答共用（FR-QA-07 / G-03）。

    置于链路最前，只写 history / history_text 两个专属字段，
    避免与三路并行召回的字段产生并发写冲突。
    """
    add_running_task(state["task_id"], "node_query_history")
    delta = load_history(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_history")
    return delta
