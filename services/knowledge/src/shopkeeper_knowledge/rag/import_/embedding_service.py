"""
向量化服务：用 BGE-M3 为切片批量生成 dense + sparse 向量。

为增强检索语义，向量输入由 `item_name + content` 拼接构成；
批处理避免长文本溢出。无模型权重时抛出明确错误（由上层降级为 failed）。
"""
from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.logging import logger

# 单批最大切片数
_BATCH_SIZE = 32


def generate_chunk_embeddings(state) -> dict:
    """
    为 state.chunks 批量生成向量，回写带 embedding 的 chunks。
    每个 chunk 增加 dense_vec / sparse_vec 字段。
    """
    chunks = state.get("chunks") or []
    item_name = state.get("item_name", "")

    if not chunks:
        return {"chunks": []}

    # 拼接 item_name 增强语义
    texts = [f"{item_name} {c.get('content', '')}".strip() for c in chunks]

    all_dense: list[list[float]] = []
    all_sparse: list[dict] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        try:
            emb = llm_provider.embed_documents(batch)
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            raise
        all_dense.extend(emb["dense"])
        all_sparse.extend(emb["sparse"])

    for c, d, s in zip(chunks, all_dense, all_sparse):
        c["dense_vec"] = d
        c["sparse_vec"] = s

    logger.info(f"向量化完成，共 {len(chunks)} 个 chunk")
    return {"chunks": chunks}
