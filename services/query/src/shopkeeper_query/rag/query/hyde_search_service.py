"""
HyDE 检索服务：先让 LLM 生成假设性答案，再用该答案做向量检索。

HyDE（Hypothetical Document Embedding）针对问句过短、语义稀疏、意图弱的场景，
通过生成一段"理想的假设答案"作为检索输入，增强查询语义表达，弥补原生问句信息量不足导致的漏召。
"""
from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger

from shopkeeper_query.infra.vectorstore.milvus_store import chunks_store


def hyde_retrieve(state) -> dict:
    """
    用 rephrased_query 生成假设答案 -> 向量化 -> Milvus 混合检索，回写 hyde_documents。
    """
    if lm_config.mock:
        return {"hyde_documents": []}

    rephrased_query = state.get("rephrased_query") or state["query"]
    hypothetical = _generate_hypothetical_doc(rephrased_query)

    hits = []
    try:
        emb = llm_provider.embed_query(hypothetical)
        query_dense = emb["dense"][0]
        query_sparse = emb["sparse"][0]
        hits = chunks_store.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            top_k=10,
            rerank="rrf",
        )
        logger.info(f"HyDE 检索 {len(hits)} 条")
    except Exception as e:
        logger.warning(f"HyDE 检索失败（降级为空候选，不影响主流程）: {e}")
        hits = []
    return {"hyde_documents": hits}


def _generate_hypothetical_doc(query: str) -> str:
    """基于问题生成一段假设性答案文本，作为 HyDE 检索输入。"""
    prompt = (
        "请针对下面这个问题，写一段尽可能具体、专业的假设性回答（2-3 句话）。\n"
        "不需要真实准确，只需要语言风格与真实资料相近，用于辅助检索。\n\n"
        f"问题：{query}"
    )
    try:
        model = llm_provider.chat()
        resp = model.invoke(prompt)
        text = (getattr(resp, "content", "") or "").strip()
        if text:
            return text
    except Exception as e:
        logger.warning(f"HyDE 假设答案生成失败，回退原问题: {e}")
    return query
