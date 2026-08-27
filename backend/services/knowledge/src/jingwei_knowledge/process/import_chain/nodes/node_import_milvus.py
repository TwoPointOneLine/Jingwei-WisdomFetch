from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.services.index_service import index_chunks
from jingwei_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_import_milvus")
def node_import_milvus(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_import_milvus")
    state = index_chunks(state)
    add_done_task(state["task_id"], "node_import_milvus")
    return state
