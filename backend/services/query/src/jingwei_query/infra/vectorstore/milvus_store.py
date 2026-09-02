"""
Milvus 向量库操作封装（infra 层）。

封装集合创建、数据插入、混合检索（稠密 + 稀疏 RRF/加权），
为导入链入库节点与查询链检索节点提供统一入口。
"""

from jingwei_common.clients.milvus_client import milvus_client
from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.config.embedding_config import embedding_config
from jingwei_common.config.milvus_config import milvus_config
from jingwei_common.constants import COLLECTION_KNOWLEDGE_ITEMS, ROLE_ADMIN, VIS_SHARED, VIS_TEAM
from jingwei_common.logging import logger, step_log
from pymilvus import (
    AnnSearchRequest,
    DataType,
    RRFRanker,
    WeightedRanker,
)

# 集合加载/恢复等待参数
_LOAD_WAIT_TIMEOUT = 120.0  # 最多等待集合从 recovering/loading 变为 Loaded 的秒数
_LOAD_POLL_INTERVAL = 2.0   # 轮询间隔秒
_RECOVERING_MARKERS = ("on recovering", "recovery", "not loaded")  # 106 错误文案命中即判定为瞬时态
_RETRY_FOR_RECOVERY = 2     # 命中 recovering 瞬时态时的最大重试次数


def _is_recovering_error(exc: Exception) -> bool:
    """判定是否为 Milvus 集合 recovering/未加载的瞬时错误（code=106 等）。"""
    msg = (getattr(exc, "message", "") or str(exc)).lower()
    return any(m in msg for m in _RECOVERING_MARKERS)


def _load_state_is_loaded(state) -> bool:
    """兼容 pymilvus 不同版本/封装：state 可能是
    - LoadState 枚举对象（name=='Loaded'）
    - {'state': <LoadState: Loaded>} 字典（MilvusClient.get_load_state 实际返回）
    - 字符串 'Loaded'
    """
    # 字典包装：{'state': <LoadState: Loaded>}
    if isinstance(state, dict):
        state = state.get("state", state)
    # 枚举：LoadState.Loaded 的 name == 'Loaded'
    name = getattr(state, "name", None)
    if isinstance(name, str):
        return name.lower() == "loaded"
    if isinstance(state, str):
        return state.lower() == "loaded"
    return False


def _with_recovery_retry(fn, store: "MilvusStore"):
    """执行 fn；若命中 recovering 瞬时错误，触发加载守卫后重试有限次。"""
    last_exc: Exception | None = None
    for attempt in range(_RETRY_FOR_RECOVERY + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 需捕获 Milvus 各种异常
            last_exc = e
            if _is_recovering_error(e):
                logger.warning(
                    f"集合 {store.collection} 处于恢复态（尝试 {attempt + 1}/"
                    f"{_RETRY_FOR_RECOVERY + 1}），触发加载守卫后重试"
                )
                store._loaded = False  # 标记失效，强制重新检查加载态
                try:
                    store._ensure_loaded()
                except Exception as le:
                    logger.warning(f"加载守卫执行失败: {le}")
                continue
            raise
    if last_exc is not None:
        raise last_exc



class MilvusStore:
    """Milvus 知识库操作封装。"""

    def __init__(self, collection_name: str | None = None):
        self.collection = collection_name or milvus_config.chunks_collection
        self.dim = embedding_config.embedding_dim
        self._loaded = False  # 本进程已成功 load 过的标记，避免每次查询都打 get_load_state

    # ---------------------- 加载态守卫（方案 B：自愈 recovering/loading） ----------------------
    def _ensure_loaded(self):
        """确保集合已 Load 进内存且不在 recovering 态。

        - 幂等：本进程已确认 Loaded 后直接返回；
        - 集合不存在时跳过（交由上层 has_collection 处理）；
        - recovering/loading 中间态：轮询等待至 Loaded 或超时。
        """
        if self._loaded:
            return
        client = milvus_client.client
        if not client.has_collection(self.collection):
            return
        try:
            state = client.get_load_state(collection_name=self.collection)
        except Exception as e:
            # 取不到加载态（如老版本 API）时退化为直接尝试 load
            logger.warning(f"获取集合加载态失败，尝试直接 load: {e}")
            state = None
        if _load_state_is_loaded(state):
            self._loaded = True
            return
        # Loading / OnRecovering / NotLoad 等：触发 load 并等待
        try:
            client.load_collection(collection_name=self.collection)
        except Exception as e:
            logger.warning(f"load_collection 触发失败（可能已在加载中）: {e}")
        self._wait_loaded()
        self._loaded = True

    def _wait_loaded(self):
        """轮询等待集合进入 Loaded，超时则抛出，交由调用方重试。"""
        import time

        client = milvus_client.client
        deadline = time.monotonic() + _LOAD_WAIT_TIMEOUT
        while time.monotonic() < deadline:
            try:
                state = client.get_load_state(collection_name=self.collection)
            except Exception:
                state = None
            if _load_state_is_loaded(state):
                return
            time.sleep(_LOAD_POLL_INTERVAL)
        raise RuntimeError(
            f"集合 {self.collection} 在 {_LOAD_WAIT_TIMEOUT}s 内未就绪"
            f"（可能仍在 recovering/loading），请稍后重试或检查 Milvus 状态"
        )

    # ---------------------- 集合管理 ----------------------
    def create_collection_if_not_exists(self):
        """创建带稠密+稀疏字段的集合（已存在则跳过）。"""
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
            # 稀疏向量：由导入链用 BGE-M3 lexical_weights 客户端生成后写入
            # （注意：部署的 Milvus 为 2.4.x，不支持 BM25 Function，故不使用服务端函数生成）
            FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR),
        ]
        schema = CollectionSchema(fields, enable_dynamic_field=True)
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
        self._ensure_loaded()

        def _do():
            client.insert(collection_name=self.collection, data=rows)
            logger.info(f"插入 {len(rows)} 条切片到 {self.collection}")

        _with_recovery_retry(_do, self)

    def flush(self):
        milvus_client.client.flush(self.collection)

    # ---------------------- 检索隔离 ----------------------
    def accessible_item_names(self, owner: str, role: str, team_id: str = "") -> list[str] | None:
        """返回某用户可检索的 item_name 列表；返回 None 表示不过滤（全量，如管理员）。

        - 管理员：None（检索全部）
        - 普通用户：自己上传的 + 共享的 + 同团队（team 可见）的
        - guest（owner 为空）：仅共享的

        可见性/归属以 Mongo knowledge_items 为准（权威来源）。
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
            return [d["item_name"] for d in docs]
        except Exception as e:
            logger.warning(f"accessible_item_names 查询失败，回退 Milvus: {e}")
        # 回退：从 Milvus 动态字段聚合（无元信息时按 owner 字段过滤）
        client = milvus_client.client
        if not client.has_collection(self.collection):
            return []

        def _do():
            return client.query(
                self.collection,
                filter="item_name != ''",
                output_fields=["item_name", "owner", "visibility", "team_id"],
                limit=10_000,
            )

        try:
            res = _with_recovery_retry(_do, self)
        except Exception as e:
            logger.warning(f"Milvus 回退查询失败，返回空列表: {e}")
            return []
        names: set[str] = set()
        for r in res:
            vis = r.get("visibility") or "private"
            if vis == VIS_SHARED or r.get("owner") == owner:
                names.add(r["item_name"])
            elif vis == VIS_TEAM and team_id and r.get("team_id") == team_id:
                names.add(r["item_name"])
        return sorted(names)

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
        self._ensure_loaded()  # 方案 B：检索前确保集合已 Load 且不在 recovering 态
        # 稀疏向量为空（如 Ollama BGE-M3 仅返回稠密）时降级为纯稠密检索
        if not query_sparse:
            results = _with_recovery_retry(
                lambda: client.search(
                    collection_name=self.collection,
                    data=[query_dense],
                    anns_field="dense_vector",
                    search_params={"metric_type": "IP", "params": {}},
                    limit=top_k,
                    filter=filter_expr or "",
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
                ),
                self,
            )
        else:
            # pymilvus 3.x：hybrid_search 需显式构造 AnnSearchRequest 列表；
            # 稀疏向量需 {int: float} 字典形式（embedding 层产出 [{"id","weight"}]）
            ranker = RRFRanker() if rerank == "rrf" else WeightedRanker(0.7, 0.3)
            sparse_data = [
                {int(d["id"]): float(d["weight"]) for d in query_sparse}
                if query_sparse and isinstance(query_sparse[0], dict) and "id" in query_sparse[0]
                else query_sparse
            ]
            reqs = [
                AnnSearchRequest(
                    data=[query_dense],
                    anns_field="dense_vector",
                    param={"metric_type": "IP", "params": {}},
                    limit=top_k,
                    filter=filter_expr or "",
                ),
                AnnSearchRequest(
                    data=sparse_data,
                    anns_field="sparse",
                    param={"metric_type": "IP", "params": {}},
                    limit=top_k,
                    filter=filter_expr or "",
                ),
            ]
            results = _with_recovery_retry(
                lambda: client.hybrid_search(
                    collection_name=self.collection,
                    reqs=reqs,
                    ranker=ranker,
                    limit=top_k,
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
                ),
                self,
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
