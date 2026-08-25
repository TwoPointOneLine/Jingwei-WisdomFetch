# shopkeeper-knowledge

掌柜智库 - 知识库导入服务（独立可部署模块）（多模块架构 · 阶段2）

## 结构

```
src/shopkeeper_knowledge/
├── api/           # FastAPI 入口（main.py: app）
├── process/       # LangGraph 编排链
├── rag/           # 核心算法服务
└── infra/         # 域内基础设施（文档解析 / 对象存储 / 向量库 / 持久化 / MCP）
```

公共能力（配置 / 日志 / 工具 / 统一 Web / 客户端 / AI）由 `shopkeeper-common` 提供。

## 本地开发

```bash
cd services/knowledge
uv sync            # 依赖根 workspace 锁
uv run uvicorn shopkeeper_knowledge.api.import_server.main:app --host 0.0.0.0 --port 8081
```

## 测试

```bash
uv run pytest
```

## 运行依赖

- 仓库根 .env（含 Milvus / MinIO / Mongo / LLM 配置），或设置 SHOPKEEPER_ROOT
