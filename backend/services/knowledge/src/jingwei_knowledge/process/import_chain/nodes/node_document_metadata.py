"""文档结构化元数据识别节点（FR-IMP-03）。"""
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.state import ImportGraphState
from jingwei_knowledge.rag.import_.metadata_service import _merge_doc_meta


def node_document_metadata(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_document_metadata")
    state = dict(state)
    state.update(_merge_doc_meta(state))
    add_done_task(state["task_id"], "node_document_metadata")
    return state
