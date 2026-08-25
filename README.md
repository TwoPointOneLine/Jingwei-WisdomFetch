# 掌柜智库 (Shopkeeper Think Tank)

企业级私有知识库智能问答系统（RAG），基于 FastAPI + LangGraph + Milvus + MongoDB + MinIO 构建。

## 技术栈

- **Web 框架**: FastAPI
- **流程编排**: LangGraph
- **向量库**: Milvus
- **持久化**: MongoDB
- **对象存储**: MinIO
- **PDF 解析**: MinerU
- **LLM**: 通义千问 (DashScope)
- **嵌入/重排**: BGE-M3 / BGE-Reranker（本地）

## 环境管理

本项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖与虚拟环境：

```bash
# 安装 uv
pip install uv

# 创建虚拟环境并安装依赖（含清华镜像源加速）
uv sync

# 安装开发依赖（pytest / ruff / httpx）
uv sync --group dev

# 运行环境自检
uv run python test/00_env_check.py
```

## 配置

复制 `deploy/.env.example` 为 `.env` 并填入真实密钥与服务地址（应用运行时从项目根目录的 `.env` 读取）：

```bash
copy deploy\.env.example .env
```

## 一键启动（本地运行）

提供一键脚本，自动检查基础设施连通性、并行拉起导入/查询两个服务并等待健康：

```bash
# 启动（先确保基础设施已启动：docker compose -f deploy\docker-compose.yml up -d）
run.bat
# 或等价命令
uv run python scripts/start_all.py

# 停止
run.bat --stop
# 或
uv run python scripts/start_all.py --stop

# 仅检查环境（不启动）
uv run python scripts/start_all.py --check
```

启动成功后访问：
- 导入服务：http://127.0.0.1:8081/html
- 查询服务：http://127.0.0.1:8082/html
- API 文档：http://127.0.0.1:8082/docs

> 端口读取自 `.env` 的 `IMPORT_APP_PORT` / `QUERY_APP_PORT`（默认 8081 / 8082）。脚本通过子进程拉起 uvicorn，日志写入 `logs/import-server.log` 与 `logs/query-server.log`。

## React 前端

前端位于 `frontend/`（Vite + React 19 + TypeScript，包管理用 pnpm），包含「智能问答」与「知识库管理」两个面板。

```bash
cd frontend
pnpm install        # 安装依赖

pnpm dev            # 开发模式（http://localhost:5173，Vite 代理转发到后端）
pnpm build          # 生产构建（产物在 frontend/dist）
```

**部署方式**：`pnpm build` 后，query 服务（8082）根路径 `/` 直接提供构建产物，浏览器访问 `http://127.0.0.1:8082/` 即为主界面。

> 环境差异：`import.meta.env.PROD` 为真（生产构建）时，前端用绝对 URL 跨域调用两个后端（CORS 已开放 `*`）；开发模式走 `/api/import`、`/api/query` 由 Vite 代理转发。

## 目录结构

见 `docs/03【掌柜智库】环境准备.md` 的「项目结构设计」。

## Docker 部署（阶段 5：全模块独立镜像 + 按需启停）

基础设施（etcd / Milvus / MongoDB / MinIO / Attu）与五个服务模块（网关/认证/用户/知识/问答）由 `deploy/compose.yml` 统一编排（`include` 合并同名目录下基础设施 `docker-compose.yml`），并支持一键部署脚本。

### 1. 一键部署（推荐）

```bash
# 复制环境变量模板（首次）
copy deploy\.env.example .env

# 构建前端 + 五服务镜像并全部启动（依赖自动拉起，等待健康检查通过）
scripts\deploy.bat up

# 按需启停：只启动网关与问答（依赖基础设施自动拉起）
scripts\deploy.bat up --services gateway,query

# 健康检查 / 查看状态 / 停止 / 清数据
scripts\deploy.bat health
scripts\deploy.bat ps
scripts\deploy.bat down
scripts\deploy.bat down --volumes
scripts\deploy.bat logs gateway
```

### 2. 手动 compose（等价）

```bash
# 构建镜像（前端 dist 由网关经 volume 挂载托管，需先构建前端：pnpm --dir frontend build）
docker compose -f deploy/compose.yml build

# 启动全部或按需（如只起网关+问答）
docker compose -f deploy/compose.yml up -d
docker compose -f deploy/compose.yml up -d gateway-server query-server

# 查看 / 停止
docker compose -f deploy/compose.yml ps
docker compose -f deploy/compose.yml down
```

### 3. 端口一览

| 端口 | 模块 | 说明 |
|---|---|---|
| 8080 | 网关 gateway-server | 统一入口（前端 + `/api/*` + `/gateway/docs`） |
| 8083 | 认证 auth-server | `/api/auth/*` |
| 8084 | 用户 user-server | `/api/user/*` |
| 8081 | 知识库 knowledge-server | `/api/knowledge/*`、`/api/import/*` |
| 8082 | 问答 query-server | `/api/query/*` |
| 8000 | Attu | Milvus Web 控制台 |
| 9001 | MinIO | 对象存储控制台 |

### 4. 关键配置

- **`.env`**：复制 `deploy/.env.example`，填入 `OPENAI_API_KEY`、`BGE_MODELS_DIR`（本机模型根目录，挂载进知识/问答容器）等；`MONGO_DB_NAME` 为共享库名，勿改动。
- **镜像**：`deploy/docker/{gateway,auth,user,knowledge,query}.Dockerfile`（uv workspace 多阶段构建，tag `shopkeeper-{module}:0.1.0`），镜像内置 `/health` 健康检查。
- **前端**：`pnpm --dir frontend build` 产出 `frontend/dist`，由网关容器挂载托管（`GATEWAY_DIST_DIR=/app/frontend/dist`）。
- **CI/CD**：`.github/workflows/ci.yml`（lint/测试/前端/打包）与 `cd.yml`（打 `v*` tag 推送五服务镜像到 GHCR）。

> 注意：Milvus standalone 内部自带一个 MinIO（端口 9200/9201），与「外部对象存储 MinIO」（9000/9001）端口已错开，避免冲突。知识/问答镜像含 torch 等推理依赖，首次构建需拉取较大依赖。

