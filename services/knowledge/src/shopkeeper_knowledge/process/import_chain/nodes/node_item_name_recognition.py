from shopkeeper_common.logging import node_log
from shopkeeper_common.web.task_utils import add_done_task, add_running_task

from shopkeeper_knowledge.process.import_chain.services.item_name_service import (
    recognize_and_index_item_name,
)
from shopkeeper_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_item_name_recognition")
def node_item_name_recognition(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_item_name_recognition")
    state = recognize_and_index_item_name(state)
    add_done_task(state["task_id"], "node_item_name_recognition")
    return state
