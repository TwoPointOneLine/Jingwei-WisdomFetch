"""
向量检索服务：用重新措辞的问句做 Milvus 混合检索（dense + sparse）。

依赖 BGE-M3 生成查询向量 + Milvus 混合索引。mock 模式或模型不可用时返回空候选，
由上层安全降级。
"""
from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger

from shopkeeper_query.infra.vectorstore.milvus_store import chunks_store


def vector_retrieve(state) -> dict:
    """
    取出 rephrased_query（回退 query）做向量召回，回写 vector_documents。
    """
    if lm_config.mock:
        return {"vector_documents": []}

    rephrased_query = state.get("rephrased_query") or state["query"]
    try:
        emb = llm_provider.embed_query(rephrased_query)
        query_dense = emb["dense"][0]
        query_sparse = emb["sparse"][0]
        hits = chunks_store.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            top_k=10,
            rerank="rrf",
        )
        logger.info(f"向量召回 {len(hits)} 条")
    except Exception as e:
        logger.warning(f"向量召回失败（降级为空候选，不影响主流程）: {e}")
        hits = []
    return {"vector_documents": hits}
