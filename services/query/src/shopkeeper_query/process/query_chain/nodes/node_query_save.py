from shopkeeper_common.logging import node_log
from shopkeeper_common.web.task_utils import add_done_task, add_running_task

from shopkeeper_query.process.query_chain.services.query_save_service import save_conversation
from shopkeeper_query.process.query_chain.state import QueryGraphState


@node_log("node_query_save")
def node_query_save(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_save")
    state = save_conversation(state)
    add_done_task(state["task_id"], "node_query_save")
    return state
