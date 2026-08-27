from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_query.process.query_chain.services.query_rerank_service import rerank_documents
from jingwei_query.process.query_chain.state import QueryGraphState


@node_log("node_query_rerank")
def node_query_rerank(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_rerank")
    delta = rerank_documents(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_rerank")
    # 仅返回增量字段，避免 fan-in（mcp/rrf 汇入）多次触发时对共享字段冲突
    return delta
