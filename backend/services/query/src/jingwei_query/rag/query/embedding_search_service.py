"""
向量检索服务：用重新措辞的问句做 Milvus 混合检索（dense + sparse）。

依赖 BGE-M3 生成查询向量 + Milvus 混合索引。mock 模式或模型不可用时返回空候选，
由上层安全降级。
"""
from jingwei_common.ai.providers import llm_provider
from jingwei_common.config import rag_config
from jingwei_common.config.lm_config import lm_config
from jingwei_common.logging import logger

from jingwei_query.infra.vectorstore.milvus_store import chunks_store


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
        # 检索隔离（多级）：本人 + 同团队(team 可见) + 共享；管理员/None 检索全部
        accessible = chunks_store.accessible_item_names(
            owner=state.get("username", "guest"),
            role=state.get("user_role", ""),
            team_id=state.get("user_team_id", ""),
        )
        filter_expr = None
        if accessible is not None:
            if not accessible:
                accessible = ["__none__"]
            safe = [f'"{n}"' for n in accessible]
            filter_expr = f"item_name in [{','.join(safe)}]"
        hits = chunks_store.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            top_k=rag_config.retrieval_top_k,
            rerank="rrf",
            filter_expr=filter_expr,
        )
        logger.info(f"向量召回 {len(hits)} 条（filter={filter_expr}）")
    except Exception as e:
        logger.warning(f"向量召回失败（降级为空候选，不影响主流程）: {e}")
        hits = []
    return {"vector_documents": hits}
