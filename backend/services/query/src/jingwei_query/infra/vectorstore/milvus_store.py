"""
Milvus 向量库操作封装（infra 层）。

封装集合创建、数据插入、混合检索（稠密 + 稀疏 RRF/加权），
为导入链入库节点与查询链检索节点提供统一入口。
"""

from jingwei_common.clients.milvus_client import milvus_client
from jingwei_common.config.embedding_config import embedding_config
from jingwei_common.config.milvus_config import milvus_config
from jingwei_common.logging import logger, step_log
from pymilvus import (
    DataType,
    Function,
    FunctionType,
    RRFRanker,
    WeightedRanker,
)


class MilvusStore:
    """Milvus 知识库操作封装。"""

    def __init__(self, collection_name: str | None = None):
        self.collection = collection_name or milvus_config.chunks_collection
        self.dim = embedding_config.embedding_dim

    # ---------------------- 集合管理 ----------------------
    def create_collection_if_not_exists(self):
        """创建带稠密+稀疏字段、BM25 函数的集合（已存在则跳过）。"""
        client = milvus_client.client
        if client.has_collection(self.collection):
            logger.info(f"集合已存在: {self.collection}")
            return
        logger.info(f"创建集合: {self.collection} (dim={self.dim})")
        from pymilvus import CollectionSchema, FieldSchema

        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="item_name", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="file_title", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            # BM25 函数输出字段（稀疏向量），必须与 Function 的 output_field_names 对应
            FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR),
        ]
        schema = CollectionSchema(
            fields,
            enable_dynamic_field=True,
            functions=[
                Function(
                    name="bm25",
                    input_field_names=["content"],
                    output_field_names="sparse",
                    function_type=FunctionType.BM25,
                )
            ],
        )
        client.create_collection(collection_name=self.collection, schema=schema)

    def drop_collection(self):
        client = milvus_client.client
        if client.has_collection(self.collection):
            client.drop_collection(self.collection)

    # ---------------------- 写入 ----------------------
    @step_log("milvus_insert")
    def insert(self, rows: list[dict]):
        """
        批量插入切片数据。
        每行需含：chunk_id, content, dense_vector, sparse_vector 及可选元数据字段。
        """
        client = milvus_client.client
        if not rows:
            return
        client.insert(collection_name=self.collection, data=rows)
        logger.info(f"插入 {len(rows)} 条切片到 {self.collection}")

    def flush(self):
        milvus_client.client.flush(self.collection)

    # ---------------------- 检索 ----------------------
    @step_log("milvus_search")
    def hybrid_search(
        self,
        query_dense: list[float],
        query_sparse: list[dict],
        top_k: int = 10,
        filter_expr: str | None = None,
        rerank: str = "rrf",
    ) -> list[dict]:
        """
        稠密 + 稀疏混合检索。
        :param rerank: "rrf"（无权重混合）或 "weighted"（需配合 weights）
        :return: [{chunk_id, content, score, ...meta}]
        """
        client = milvus_client.client
        ranker = RRFRanker() if rerank == "rrf" else WeightedRanker(0.7, 0.3)
        results = client.hybrid_search(
            collection_name=self.collection,
            ann_fields=["dense_vector"],
            sparse_vector_fields=["sparse"],
            sparse_data=[query_sparse],
            dense_data=[query_dense],
            ranker=ranker,
            limit=top_k,
            filter=filter_expr,
            output_fields=[
                "chunk_id",
                "content",
                "item_name",
                "title",
                "file_title",
                "content_type",
                "product_name",
                "product_code",
                "risk_level",
                "publish_date",
                "source_file",
            ],
        )
        hits = results[0] if results else []
        return [
            {
                "chunk_id": h.get("chunk_id"),
                "content": h.get("content"),
                "item_name": h.get("item_name"),
                "title": h.get("title"),
                "file_title": h.get("file_title"),
                "score": h.distance,
            }
            for h in hits
        ]


# 默认集合快捷实例
chunks_store = MilvusStore(milvus_config.chunks_collection)
entity_store = MilvusStore(milvus_config.entity_name_collection)
item_store = MilvusStore(milvus_config.item_name_collection)
