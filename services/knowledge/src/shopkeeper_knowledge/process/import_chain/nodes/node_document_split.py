from shopkeeper_common.logging import node_log
from shopkeeper_common.web.task_utils import add_done_task, add_running_task

from shopkeeper_knowledge.process.import_chain.services.split_service import split_document
from shopkeeper_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_document_split")
def node_document_split(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_document_split")
    state = split_document(state)
    add_done_task(state["task_id"], "node_document_split")
    return state
