"""配置层：基础配置与原子配置单例。

- common.py          环境变量加载与类型安全读取、项目根定位
- settings_config    应用基础设置（端口/应用名）
- lm_config          LLM 配置（dashscope / local / mock）
- embedding_config   BGE-M3 向量配置
- milvus_config      Milvus 向量库配置
- mineru_config      MinerU PDF 解析配置
- minio_config       MinIO 对象存储配置
- reranker_config    BGE-Reranker 重排模型路径配置
- rag_config         RAG 检索/融合/精排/多轮参数（top_k、阈值等）
- bailian_mcp_config 联网搜索 MCP 配置
- providers          InfraConfig 聚合门面（统一配置访问入口）

约定：业务代码统一通过 `jingwei_common.config.infra_config`
或对应分组单例访问配置，不直接读取环境变量。
"""
from jingwei_common.config.bailian_mcp_config import MCPConfig, mcp_config
from jingwei_common.config.embedding_config import EmbeddingConfig, embedding_config
from jingwei_common.config.lm_config import LMConfig, lm_config
from jingwei_common.config.milvus_config import MilvusConfig, milvus_config
from jingwei_common.config.mineru_config import MinerUConfig, mineru_config
from jingwei_common.config.minio_config import MinioConfig, minio_config
from jingwei_common.config.providers import InfraConfig, infra_config
from jingwei_common.config.rag_config import RagConfig, rag_config
from jingwei_common.config.reranker_config import RerankerConfig, reranker_config
from jingwei_common.config.settings_config import SettingsConfig, settings

__all__ = [
    "InfraConfig",
    "infra_config",
    "SettingsConfig",
    "settings",
    "LMConfig",
    "lm_config",
    "EmbeddingConfig",
    "embedding_config",
    "MilvusConfig",
    "milvus_config",
    "MinerUConfig",
    "mineru_config",
    "MinioConfig",
    "minio_config",
    "RerankerConfig",
    "reranker_config",
    "RagConfig",
    "rag_config",
    "MCPConfig",
    "mcp_config",
]
