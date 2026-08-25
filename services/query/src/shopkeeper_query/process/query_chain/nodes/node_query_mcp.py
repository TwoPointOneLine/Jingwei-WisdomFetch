from shopkeeper_common.logging import node_log
from shopkeeper_common.web.task_utils import add_done_task, add_running_task

from shopkeeper_query.process.query_chain.services.query_mcp_service import web_search
from shopkeeper_query.process.query_chain.state import QueryGraphState


@node_log("node_query_mcp")
def node_query_mcp(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_mcp")
    delta = web_search(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_mcp")
    return delta
