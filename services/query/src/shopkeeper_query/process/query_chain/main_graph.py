"""
查询链主图（LangGraph）。

节点顺序（三路召回 → RRF 融合 → 全局精排 → 生成）：
node_query_rewrite -> (node_query_vector, node_query_hyde, node_query_mcp) 三路并行
-> node_query_rrf (融合 vector + hyde) + node_query_mcp (外网独立)
-> node_query_rerank (RRF 本地结果 + 外网结果统一精排)
-> node_query_rag -> node_query_save -> END

并行安全：
- 三路召回节点各自返回专属 list 字段（vector_documents/hyde_documents/web_documents）；
- fan-in 融合节点（rrf/rerank）返回各自专属字段（rrf_documents/rerank_documents）；
- state 中对所有会被并发/多次写入的字段配置了"后写覆盖"reducer（Annotated[_last_write_wins]），
  因此即使 fan-in 节点被多次触发，写入也能安全合并，不会抛 INVALID_CONCURRENT_GRAPH_UPDATE。
"""
from langgraph.graph import END, StateGraph

from shopkeeper_query.process.query_chain.nodes.node_query_hyde import node_query_hyde
from shopkeeper_query.process.query_chain.nodes.node_query_mcp import node_query_mcp
from shopkeeper_query.process.query_chain.nodes.node_query_rag import node_query_rag
from shopkeeper_query.process.query_chain.nodes.node_query_rerank import node_query_rerank
from shopkeeper_query.process.query_chain.nodes.node_query_rewrite import node_query_rewrite
from shopkeeper_query.process.query_chain.nodes.node_query_rrf import node_query_rrf
from shopkeeper_query.process.query_chain.nodes.node_query_save import node_query_save
from shopkeeper_query.process.query_chain.nodes.node_query_vector import node_query_vector
from shopkeeper_query.process.query_chain.state import QueryGraphState

workflow = StateGraph(QueryGraphState)

workflow.add_node("node_query_rewrite", node_query_rewrite)
workflow.add_node("node_query_vector", node_query_vector)
workflow.add_node("node_query_hyde", node_query_hyde)
workflow.add_node("node_query_mcp", node_query_mcp)
workflow.add_node("node_query_rrf", node_query_rrf)
workflow.add_node("node_query_rerank", node_query_rerank)
workflow.add_node("node_query_rag", node_query_rag)
workflow.add_node("node_query_save", node_query_save)

workflow.set_entry_point("node_query_rewrite")

# 三路并行召回
workflow.add_edge("node_query_rewrite", "node_query_vector")
workflow.add_edge("node_query_rewrite", "node_query_hyde")
workflow.add_edge("node_query_rewrite", "node_query_mcp")

# 两路本地召回先 RRF 融合
workflow.add_edge("node_query_vector", "node_query_rrf")
workflow.add_edge("node_query_hyde", "node_query_rrf")

# RRF 本地结果 + 外网结果统一精排
workflow.add_edge("node_query_mcp", "node_query_rerank")
workflow.add_edge("node_query_rrf", "node_query_rerank")

workflow.add_edge("node_query_rerank", "node_query_rag")
workflow.add_edge("node_query_rag", "node_query_save")
workflow.add_edge("node_query_save", END)

kb_query_app = workflow.compile()
