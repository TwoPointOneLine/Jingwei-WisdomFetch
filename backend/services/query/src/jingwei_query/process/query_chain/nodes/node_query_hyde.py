from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_query.process.query_chain.services.query_hyde_service import hyde_retrieve
from jingwei_query.process.query_chain.state import QueryGraphState


@node_log("node_query_hyde")
def node_query_hyde(state: QueryGraphState) -> QueryGraphState:
    add_running_task(state["task_id"], "node_query_hyde")
    delta = hyde_retrieve(state)
    state.update(delta)
    add_done_task(state["task_id"], "node_query_hyde")
    # 仅返回增量字段，避免并行分支合并时对共享字段冲突
    return delta
