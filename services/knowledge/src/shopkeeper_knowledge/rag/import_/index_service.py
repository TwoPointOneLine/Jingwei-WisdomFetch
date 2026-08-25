"""
入库服务：按 item_name 幂等清理旧数据后，批量写入 Milvus 并回填 chunk_id。

流程：
  - 用 item_name 过滤，删除该主体历史切片（幂等）；
  - 确保 collection 存在且 schema + 混合索引（BM25 稀疏）就绪；
  - 批量插入，并将 Milvus 返回的 primary key 回填到 chunk_id。
"""
from shopkeeper_common.clients.milvus_client import milvus_client
from shopkeeper_common.logging import logger

from shopkeeper_knowledge.infra.vectorstore.milvus_store import chunks_store


def index_chunks(state) -> dict:
    """
    把 state.chunks（已带向量）写入 Milvus，回写写入条数 done_count。
    """
    chunks = state.get("chunks") or []
    item_name = state.get("item_name", "")

    if not chunks:
        return {"done_count": 0}

    # 幂等：清理该 item_name 旧数据
    try:
        client = milvus_client.client
        if client.has_collection(chunks_store.collection):
            client.delete(
                collection_name=chunks_store.collection,
                filter=f'item_name == "{item_name}"',
            )
    except Exception as e:
        logger.warning(f"清理旧数据失败（首次入库可忽略）: {e}")

    # 确保 collection 存在（含 BM25 稀疏索引）
    try:
        chunks_store.create_collection_if_not_exists()
    except Exception as e:
        logger.error(f"Milvus 集合准备失败: {e}")
        raise

    # 组装 Milvus 写入行（字段需与 schema 对齐）
    rows = []
    for c in chunks:
        rows.append(
            {
                "chunk_id": c.get("chunk_id") or "",
                "content": c.get("content", ""),
                "item_name": item_name,
                "title": c.get("title", ""),
                "file_title": c.get("file_title", ""),
                "dense_vector": c.get("dense_vec") or [],
                "sparse": c.get("sparse_vec") or [],
            }
        )

    # 批量插入
    try:
        chunks_store.insert(rows)
        milvus_client.client.flush(chunks_store.collection)
    except Exception as e:
        logger.error(f"Milvus 批量插入失败: {e}")
        raise

    # 用 item_name 回查写入记录，回填 chunk_id（Milvus 限制主键不可预测，故回查）
    try:
        res = milvus_client.client.query(
            collection_name=chunks_store.collection,
            filter=f'item_name == "{item_name}"',
            output_fields=["chunk_id", "content"],
        )
        by_content = {r["content"]: r["chunk_id"] for r in res}
        for c in chunks:
            cid = by_content.get(c.get("content"))
            if cid:
                c["chunk_id"] = cid
    except Exception as e:
        logger.warning(f"chunk_id 回填失败（使用本地 hash 作为 id）: {e}")

    logger.info(f"入库完成，item_name={item_name}, 写入 {len(chunks)} 条")
    return {"done_count": len(chunks)}
