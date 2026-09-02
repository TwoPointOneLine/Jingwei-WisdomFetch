"""
查询链主图（LangGraph）。

节点顺序（历史 → 改写 → 三路召回 → RRF 融合 → 全局精排 → 生成）：
node_query_history -> node_query_rewrite
-> (node_query_vector, node_query_hyde, node_query_mcp) 三路并行
-> node_query_rrf (融合 vector + hyde；mcp 的 web_documents 已在共享 state 中)
-> node_query_rerank (RRF 本地结果 + 外网结果统一精排)
-> node_query_rag -> node_query_save -> END

并行安全：
- 三路召回节点各自返回专属 list 字段（vector_documents/hyde_documents/web_documents）；
- fan-in 融合节点（rrf/rerank）返回各自专属字段（rrf_documents/rerank_documents）；
- state 中对所有会被并发/多次写入的字段配置了"后写覆盖"reducer（Annotated[_last_write_wins]），
  因此即使 fan-in 节点被多次触发，写入也能安全合并，不会抛 INVALID_CONCURRENT_GRAPH_UPDATE。
"""
from langgraph.graph import END, StateGraph

from jingwei_query.process.query_chain.nodes.node_query_history import node_query_history
from jingwei_query.process.query_chain.nodes.node_query_hyde import node_query_hyde
from jingwei_query.process.query_chain.nodes.node_query_mcp import node_query_mcp
from jingwei_query.process.query_chain.nodes.node_query_rag import node_query_rag
from jingwei_query.process.query_chain.nodes.node_query_rerank import node_query_rerank
from jingwei_query.process.query_chain.nodes.node_query_rewrite import node_query_rewrite
from jingwei_query.process.query_chain.nodes.node_query_rrf import node_query_rrf
from jingwei_query.process.query_chain.nodes.node_query_save import node_query_save
from jingwei_query.process.query_chain.nodes.node_query_vector import node_query_vector
from jingwei_query.process.query_chain.state import QueryGraphState

workflow = StateGraph(QueryGraphState)

workflow.add_node("node_query_history", node_query_history)
workflow.add_node("node_query_rewrite", node_query_rewrite)
workflow.add_node("node_query_vector", node_query_vector)
workflow.add_node("node_query_hyde", node_query_hyde)
workflow.add_node("node_query_mcp", node_query_mcp)
workflow.add_node("node_query_rrf", node_query_rrf)
workflow.add_node("node_query_rerank", node_query_rerank)
workflow.add_node("node_query_rag", node_query_rag)
workflow.add_node("node_query_save", node_query_save)

# G-03：先取历史，再改写（改写需要历史做指代消解）
workflow.set_entry_point("node_query_history")
workflow.add_edge("node_query_history", "node_query_rewrite")

# 三路并行召回
workflow.add_edge("node_query_rewrite", "node_query_vector")
workflow.add_edge("node_query_rewrite", "node_query_hyde")
workflow.add_edge("node_query_rewrite", "node_query_mcp")

# 两路本地召回先 RRF 融合
workflow.add_edge("node_query_vector", "node_query_rrf")
workflow.add_edge("node_query_hyde", "node_query_rrf")

# 精排：唯一前驱为 rrf（避免 mcp 早完成时提前触发空候选执行）。
# web_documents 由 mcp 在同一 superstep 写入共享 state，rerank 直接读取即可。
workflow.add_edge("node_query_rrf", "node_query_rerank")

workflow.add_edge("node_query_rerank", "node_query_rag")
workflow.add_edge("node_query_rag", "node_query_save")
workflow.add_edge("node_query_save", END)

kb_query_app = workflow.compile()
