# shopkeeper-common

掌柜智库（Shopkeeper Think Tank）**公共模块**：所有服务模块共享的技术底座，不包含业务逻辑。

## 能力清单

| 子包 | 能力 |
|---|---|
| `config` | `.env` 加载、类型安全 env 读取、基础配置对象、`infra_config` 聚合门面 |
| `constants` | 全局常量：任务状态、SSE 事件、错误码、Mongo 集合名、角色 |
| `utils` | 通用工具：路径、时间、字符串、文件、md5、文本分块、safe_get |
| `logging` | 统一日志（loguru 封装、UTF-8 安全、调用位置修正） |
| `web` | SSE 队列/生成器、任务状态追踪、统一响应模型、异常体系 |
| `clients` | 基础客户端：MongoDB / Milvus / MinIO（懒加载单例） |
| `ai` | LLM / Embedding / Reranker 封装（Ollama / DashScope / mock 多 provider） |
| `protocols` | 服务间共享契约：统一响应 `{code,message,data}`、错误码、异常 |
| `resources` | 提示词等静态资源 |

## 使用

```bash
# 开发安装（workspace 内）
uv sync

# 单独测试
cd packages/common && uv run pytest

# 打包
uv build --package shopkeeper-common
```

```python
from shopkeeper_common.config import infra_config
from shopkeeper_common.logging import logger
from shopkeeper_common.utils import md5, chunk_text, safe_get
from shopkeeper_common.web import TaskTracker, sse_event, sse_generator
from shopkeeper_common.clients import mongo_client, milvus_store, minio_store
from shopkeeper_common.ai import llm_provider, embed_documents, embed_query, compute_rerank_score
from shopkeeper_common.protocols import ApiResponse, ApiError
```

## 设计约束

- 不包含任何业务逻辑；业务能力由服务模块（auth / user / knowledge / query）实现。
- 所有模块只能依赖本模块，本模块不依赖任何业务模块。
- 提示词等静态资源集中在 `resources/prompts/`。
