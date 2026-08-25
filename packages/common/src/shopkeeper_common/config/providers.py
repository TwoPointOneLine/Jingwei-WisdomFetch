"""
基础设施配置汇聚（统一出口门面层）。

把分散在各 config 类的配置单例汇聚到一个 InfraConfig 对象，
业务代码统一通过 `infra_config.xxx` 访问，避免到处散落 import。
"""
from dataclasses import dataclass, field

from shopkeeper_common.config.bailian_mcp_config import mcp_config
from shopkeeper_common.config.embedding_config import embedding_config
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.config.milvus_config import milvus_config
from shopkeeper_common.config.mineru_config import mineru_config
from shopkeeper_common.config.minio_config import minio_config
from shopkeeper_common.config.reranker_config import reranker_config
from shopkeeper_common.config.settings_config import settings


@dataclass
class InfraConfig:
    app: object = field(default_factory=lambda: settings)
    llm: object = field(default_factory=lambda: lm_config)
    embedding: object = field(default_factory=lambda: embedding_config)
    reranker: object = field(default_factory=lambda: reranker_config)
    mcp: object = field(default_factory=lambda: mcp_config)
    milvus: object = field(default_factory=lambda: milvus_config)
    mineru: object = field(default_factory=lambda: mineru_config)
    minio: object = field(default_factory=lambda: minio_config)


infra_config = InfraConfig()

if __name__ == "__main__":
    print(infra_config.app.import_app_name)
