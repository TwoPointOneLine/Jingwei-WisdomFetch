"""
Milvus 向量库配置。

对应 .env 中 Milvus 连接与集合名称字段。
本地直接运行用 127.0.0.1；Docker 容器内运行用服务名 milvus。
"""
from jingwei_common.config.common import env_str


class MilvusConfig:
    # Milvus 服务地址（含协议与端口）
    milvus_url: str = env_str("MILVUS_URL", "http://127.0.0.1:19530")
    # 文档切块集合
    chunks_collection: str = env_str("CHUNKS_COLLECTION", "kb_chunks")
    # 实体名（主体名）集合
    entity_name_collection: str = env_str("ENTITY_NAME_COLLECTION", "kb_entity_names")
    # 条目名集合
    item_name_collection: str = env_str("ITEM_NAME_COLLECTION", "kb_item_names")


milvus_config = MilvusConfig()
