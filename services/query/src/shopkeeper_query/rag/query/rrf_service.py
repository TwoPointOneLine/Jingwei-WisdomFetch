"""
RRF 融合服务：对两路本地向量召回（向量检索 + HyDE 检索）做 Reciprocal Rank Fusion。

RRF（Reciprocal Rank Fusion）通过 rank 倒数加权，对同时在两路召回中排名靠前的切片增强，
合并去重、择优打分，输出稳定的本地最优候选集合。外网结果独立保留，统一由 rerank 精排。
"""
from shopkeeper_common.logging import logger

# RRF 融合常数（越大则排序差异影响越平滑，常用 60）
_RRF_K = 60


def _doc_key(doc: dict) -> str:
    """文档去重键：优先用 chunk_id / url / id，退化到 content 指纹。"""
    for key in ("chunk_id", "id", "url"):
        if doc.get(key):
            return f"{key}:{doc[key]}"
    return f"content:{hash(doc.get('content') or '')}"


def fuse_by_rrf(state) -> dict:
    """
    合并 vector_documents + hyde_documents 两路本地召回，应用 RRF 算法，
    按得分降序输出 rrf_documents。
    """
    vector_docs = state.get("vector_documents") or []
    hyde_docs = state.get("hyde_documents") or []

    if not vector_docs and not hyde_docs:
        logger.warning("RRF 融合：两路本地召回均为空")
        return {"rrf_documents": []}

    rank_map: dict[str, list[int]] = {}
    doc_map: dict[str, dict] = {}

    for docs in (vector_docs, hyde_docs):
        for rank, doc in enumerate(docs, start=1):
            key = _doc_key(doc)
            doc_map.setdefault(key, doc)
            rank_map.setdefault(key, []).append(rank)

    scored = []
    for key, ranks in rank_map.items():
        score = sum(1.0 / (_RRF_K + r) for r in ranks)
        doc = dict(doc_map[key])
        doc["rrf_score"] = round(score, 6)
        doc["source"] = "milvus"
        scored.append(doc)

    scored.sort(key=lambda d: d["rrf_score"], reverse=True)
    logger.info(f"RRF 融合完成，共 {len(scored)} 条")
    return {"rrf_documents": scored}
