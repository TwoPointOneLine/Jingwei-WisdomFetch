from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_query.process.query_chain.services.query_vector_service import vector_retrieve
from jingwei_query.process.query_chain.state import QueryGraphState


@node_log("node_query_vector")
def node_query_vector(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_vector")
    delta = vector_retrieve(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_vector")
    return delta
