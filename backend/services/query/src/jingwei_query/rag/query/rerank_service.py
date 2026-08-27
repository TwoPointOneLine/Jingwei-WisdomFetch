"""
重排服务：用 BGE-Reranker 对 RRF 本地融合结果 + 联网搜索结果统一打分排序。

将本地候选（RRF 融合输出）与外部候选（MCP 联网）纳入同一语义评分体系，
通过重排模型逐一精排，过滤噪声、修正排序偏差，输出可直接用于生成的高纯净上下文。
"""
from jingwei_common.ai.providers import llm_provider
from jingwei_common.logging import logger

# 精排后保留的最大上下文条数
_RERANK_TOP_K = 5


def rerank_documents(state) -> dict:
    """
    合并 rrf_documents（本地）+ web_documents（外网），调用重排模型打分，
    按分数排序取 Top5，回写 rerank_documents。
    """
    query = state.get("rephrased_query") or state["query"]
    rrf_docs = state.get("rrf_documents") or []
    web_docs = state.get("web_documents") or []

    candidates = []
    pairs = []
    for d in rrf_docs:
        content = d.get("content") or ""
        if content.strip():
            candidates.append({**d, "source": "milvus"})
            pairs.append([query, content])
    for w in web_docs:
        snippet = w.get("snippet") or ""
        if snippet.strip():
            candidates.append({**w, "source": "web", "content": snippet})
            pairs.append([query, snippet])

    if not pairs:
        logger.warning("重排：无候选文档")
        return {"rerank_documents": []}

    try:
        scores = llm_provider.compute_rerank_score(pairs, normalize=True)
    except Exception as e:
        logger.warning(f"重排模型不可用，退化为粗排: {e}")
        top = candidates[:_RERANK_TOP_K]
        for c in top:
            c["rerank_score"] = 0.0
        logger.info(f"重排（退化）完成，Top{len(top)}")
        return {"rerank_documents": top}

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    reranked = []
    for c, s in scored[:_RERANK_TOP_K]:
        c = dict(c)
        c["rerank_score"] = float(s)
        reranked.append(c)
    logger.info(f"重排完成，Top{len(reranked)}")
    return {"rerank_documents": reranked}
