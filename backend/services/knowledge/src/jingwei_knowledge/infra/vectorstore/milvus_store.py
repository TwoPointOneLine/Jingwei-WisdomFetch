"""
Milvus 向量库操作封装（infra 层）。

封装集合创建、数据插入、混合检索（稠密 + 稀疏 RRF/加权），
为导入链入库节点与查询链检索节点提供统一入口。
"""

from jingwei_common.clients.milvus_client import milvus_client
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.config.embedding_config import embedding_config
from jingwei_common.config.milvus_config import milvus_config
from jingwei_common.constants import (
    COLLECTION_KNOWLEDGE_ITEMS,
    ROLE_ADMIN,
    VIS_PRIVATE,
    VIS_SHARED,
    VIS_TEAM,
)
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

    # ---------------------- 资料级管理（FR-IMP-05 下线/版本管理） ----------------------
    def list_items(self, owner: str | None = None, role: str | None = None, team_id: str = "") -> list[dict]:
        """列出已导入资料（按 item_name 聚合，含 chunk 数与来源文件名）。

        owner/role/team_id 用于隔离（多级）：
          - 管理员（role==ROLE_ADMIN）或 owner=None 时返回全部；
          - 普通用户仅返回「自己上传的」「共享(visibility=shared)」「同团队(visibility=team)」的资料。

        归属/可见性以 Mongo knowledge_items 为准（权威来源，切换可见性即时生效）。
        """
        client = milvus_client.client
        if not client.has_collection(self.collection):
            return []

        # 1) 从 Milvus 聚合 chunk 维度（数量、来源、结构化字段）
        res = client.query(
            self.collection,
            expr="item_name != ''",
            output_fields=["item_name", "source_file", "product_name", "publish_date"],
            limit=10_000,
        )
        agg: dict[str, dict] = {}
        for r in res:
            name = r.get("item_name") or "未命名"
            entry = agg.setdefault(
                name,
                {
                    "item_name": name,
                    "chunk_count": 0,
                    "source_files": set(),
                    "product_name": r.get("product_name", ""),
                    "publish_date": r.get("publish_date", ""),
                    "owner": "",
                    "visibility": VIS_PRIVATE,
                    "team_id": "",
                },
            )
            entry["chunk_count"] += 1
            sf = r.get("source_file")
            if sf:
                entry["source_files"].add(sf)

        # 2) 从 Mongo 叠加权威 owner/visibility/team_id
        meta: dict[str, dict] = {}
        try:
            docs = mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).find(
                {}, {"item_name": 1, "owner": 1, "visibility": 1, "team_id": 1}
            )
            for d in docs:
                meta[d["item_name"]] = {
                    "owner": d.get("owner", ""),
                    "visibility": d.get("visibility", VIS_PRIVATE),
                    "team_id": d.get("team_id", ""),
                }
        except Exception as e:
            logger.warning(f"读取资料元信息失败（使用 Milvus 默认）: {e}")

        items = []
        for e in agg.values():
            m = meta.get(e["item_name"])
            if m:
                e["owner"] = m["owner"]
                e["visibility"] = m["visibility"]
                e["team_id"] = m["team_id"]
            e["source_files"] = sorted(e["source_files"])
            # 隔离过滤（多级）：本人 / 共享 / 同团队
            if owner and role != ROLE_ADMIN:
                accessible = (
                    e["owner"] == owner
                    or e.get("visibility") == VIS_SHARED
                    or (e.get("visibility") == VIS_TEAM and team_id and e.get("team_id") == team_id)
                )
                if not accessible:
                    continue
            items.append(e)
        return items

    def accessible_item_names(self, owner: str, role: str, team_id: str = "") -> list[str] | None:
        """返回某用户可检索的 item_name 列表；返回 None 表示不过滤（全量，如管理员）。

        - 管理员：None（检索全部）
        - 普通用户：自己上传的 + 共享的 + 同团队（team 可见）的
        - guest（owner 为空）：仅共享的

        可见性/归属以 Mongo knowledge_items 为准（权威来源），切换可见性无需重向量化。
        """
        if role == ROLE_ADMIN:
            return None
        try:
            col = mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS)
            conds: list[dict] = [{"visibility": VIS_SHARED}]
            if owner:
                conds.append({"owner": owner})
                if team_id:
                    conds.append({"visibility": VIS_TEAM, "team_id": team_id})
            docs = col.find({"$or": conds}, {"item_name": 1})
            names = [d["item_name"] for d in docs]
        except Exception as e:
            logger.warning(f"accessible_item_names 查询失败，回退 Milvus: {e}")
            items = self.list_items(owner=owner, role=role, team_id=team_id)
            names = [e["item_name"] for e in items]
        return names

    def delete_item(self, item_name: str) -> int:
        """下线某资料：删除该 item_name 下的全部 chunk（FR-IMP-05）。

        同时清理 Mongo 资料元信息。返回删除的 chunk 条数。用于资料过期/错误导入的清理。
        """
        client = milvus_client.client
        if not client.has_collection(self.collection):
            return 0
        res = client.delete(self.collection, expr=f'item_name == "{item_name}"')
        deleted = res.get("delete_count", 0) if isinstance(res, dict) else 0
        # 同步清理 Mongo 资料元信息
        try:
            mongo_client.get_collection(COLLECTION_KNOWLEDGE_ITEMS).delete_one({"item_name": item_name})
        except Exception as e:
            logger.warning(f"清理资料元信息失败（可忽略）: {e}")
        logger.info(f"下线资料 item_name={item_name}，删除 chunk 数={deleted}")
        return deleted

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
            output_fields=["chunk_id", "content", "item_name", "title", "file_title"],
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
