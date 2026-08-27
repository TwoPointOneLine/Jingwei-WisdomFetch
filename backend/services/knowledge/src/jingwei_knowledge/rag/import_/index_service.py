"""
入库服务：按 item_name 幂等清理旧数据后，批量写入 Milvus 并回填 chunk_id。

流程：
  - 用 item_name 过滤，删除该主体历史切片（幂等）；
  - 确保 collection 存在且 schema + 混合索引（BM25 稀疏）就绪；
  - 批量插入，并将 Milvus 返回的 primary key 回填到 chunk_id。
"""
from datetime import UTC

from jingwei_common.clients.milvus_client import milvus_client
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.constants import (
    COLLECTION_KNOWLEDGE_ITEMS,
    VIS_PRIVATE,
    VIS_TEAM,
)
from jingwei_common.logging import logger

from jingwei_knowledge.infra.vectorstore.milvus_store import chunks_store


def index_chunks(state) -> dict:
    """
    把 state.chunks（已带向量）写入 Milvus，回写写入条数 done_count。
    """
    chunks = state.get("chunks") or []
    item_name = state.get("item_name", "")
    owner = state.get("owner", "") or ""
    visibility = state.get("visibility", VIS_PRIVATE) or VIS_PRIVATE
    team_id = state.get("team_id", "") or ""

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

    # 组装 Milvus 写入行（schema 为动态字段，doc_meta 内的结构化字段自动存储）
    rows = []
    for c in chunks:
        meta = c.get("doc_meta") or {}
        rows.append(
            {
                "chunk_id": c.get("chunk_id") or "",
                "content": c.get("content", ""),
                "item_name": item_name,
                "title": c.get("title", ""),
                "file_title": c.get("file_title", ""),
                "dense_vector": c.get("dense_vec") or [],
                "sparse": c.get("sparse_vec") or [],
                # FR-IMP-03 结构化字段（动态字段落库）
                "content_type": meta.get("content_type", ""),
                "product_name": meta.get("product_name", ""),
                "product_code": meta.get("product_code", ""),
                "risk_level": meta.get("risk_level", ""),
                "publish_date": meta.get("publish_date", ""),
                "source_file": meta.get("source_file", ""),
                # 普通用户知识库隔离：owner + 可见性 + 团队空间
                "owner": owner,
                "visibility": visibility,
                "team_id": team_id if visibility == VIS_TEAM else "",
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

    # 资料级元信息落 Mongo（owner/visibility），供列表、隔离与检索过滤使用
    try:
        source_files = sorted(
            {c.get("doc_meta", {}).get("source_file", "") for c in chunks if c.get("doc_meta", {}).get("source_file")}
        )
        mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).update_one(
            {"item_name": item_name},
            {
                "$set": {
                    "item_name": item_name,
                    "owner": owner,
                    "visibility": visibility,
                    "team_id": team_id if visibility == VIS_TEAM else "",
                    "source_files": source_files,
                    "chunk_count": len(chunks),
                    "updated_at": UTC.now(),
                },
                "$setOnInsert": {"created_at": UTC.now()},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"资料元信息写入 Mongo 失败（不影响检索）: {e}")

    logger.info(f"入库完成，item_name={item_name}, 写入 {len(chunks)} 条, owner={owner}, visibility={visibility}")
    return {"done_count": len(chunks)}
