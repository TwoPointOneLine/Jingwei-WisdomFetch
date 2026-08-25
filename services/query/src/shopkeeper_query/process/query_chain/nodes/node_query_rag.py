from shopkeeper_common.logging import node_log
from shopkeeper_common.web.task_utils import add_done_task, add_running_task

from shopkeeper_query.process.query_chain.services.query_rag_service import llm_answer
from shopkeeper_query.process.query_chain.state import QueryGraphState


@node_log("node_query_rag")
def node_query_rag(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_rag")
    delta = llm_answer(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_rag")
    # 仅返回增量字段，避免 fan-in 多次触发时对共享字段冲突
    return delta
