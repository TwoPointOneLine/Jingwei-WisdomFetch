from shopkeeper_common.logging import node_log
from shopkeeper_common.web.task_utils import add_done_task, add_running_task

from shopkeeper_knowledge.process.import_chain.services.entry_service import resolve_input_file
from shopkeeper_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_entry")
def node_entry(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_entry")
    state = resolve_input_file(state)
    add_done_task(state["task_id"], "node_entry")
    return state
