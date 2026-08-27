from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_query.process.query_chain.services.query_rrf_service import fuse_by_rrf
from jingwei_query.process.query_chain.state import QueryGraphState


@node_log("node_query_rrf")
def node_query_rrf(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_rrf")
    delta = fuse_by_rrf(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_rrf")
    return delta
