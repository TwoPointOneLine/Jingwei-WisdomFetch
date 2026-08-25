"""shopkeeper-common：掌柜智库公共模块。

提供所有服务模块共享的基础能力：
- config    基础配置（.env 加载、类型安全读取、聚合门面）
- constants 全局常量
- utils     通用工具
- logging   统一日志
- web       SSE / 任务追踪 / 统一响应 / 异常
- clients   MongoDB / Milvus / MinIO 客户端
- ai        LLM / Embedding / Reranker 封装
- auth      认证客户端与授权工具（服务间鉴权）
- protocols 服务间共享契约
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
