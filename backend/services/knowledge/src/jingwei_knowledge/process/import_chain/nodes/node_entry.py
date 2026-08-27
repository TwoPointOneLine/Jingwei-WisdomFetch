from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.services.entry_service import resolve_input_file
from jingwei_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_entry")
def node_entry(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_entry")
    state = resolve_input_file(state)
    add_done_task(state["task_id"], "node_entry")
    return state
