from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.services.embedding_service import (
    generate_chunk_embeddings,
)
from jingwei_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_bge_embedding")
def node_bge_embedding(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_bge_embedding")
    state = generate_chunk_embeddings(state)
    add_done_task(state["task_id"], "node_bge_embedding")
    return state
