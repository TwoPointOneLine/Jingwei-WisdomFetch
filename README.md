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

提供一键脚本，自动检查基础设施（Milvus / MongoDB / MinIO）连通性、并行拉起**网关 + 认证 + 用户 + 知识 + 问答五个服务**并等待健康：

```bash
# 最简一键（双击 run_backend.bat）：自动拉起基础设施(docker compose) + 五大后端服务，前台常驻，Ctrl+C 停止
run_backend.bat

# 或手动分步：
# 1) 先拉起基础设施（Docker）
docker compose -f deploy\docker-compose.yml up -d
# 2) 启动全部服务（前台常驻，Ctrl+C 停止）；--with-infra 可合并第 1 步
run.bat
run.bat --with-infra
uv run python scripts/start_all.py --with-infra

# 停止（按端口清理进程）
run.bat --stop
uv run python scripts/start_all.py --stop

# 仅检查环境（不启动）
uv run python scripts/start_all.py --check
```

启动成功后，所有流量走**网关统一入口（8080）**：
- 前端主界面：http://127.0.0.1:8080/
- 网关 API 文档：http://127.0.0.1:8080/gateway/docs
- 各后端服务文档：http://127.0.0.1:8083/docs（认证）、http://127.0.0.1:8084/docs（用户）、http://127.0.0.1:8081/html（知识导入）、http://127.0.0.1:8082/html（问答）
- 业务 API 前缀：`/api/auth/*`、`/api/user/*`、`/api/knowledge/*`、`/api/import/*`、`/api/query/*`

> 端口读取自 `.env` 的 `GATEWAY_APP_PORT / AUTH_APP_PORT / USER_APP_PORT / IMPORT_APP_PORT / QUERY_APP_PORT`（默认 8080 / 8083 / 8084 / 8081 / 8082）。脚本通过子进程拉起 uvicorn，日志写入 `logs/*.log`。

## React 前端

前端位于 `frontend/`（Vite + React 19 + TypeScript，包管理用 pnpm），包含「智能问答」与「知识库管理」两个面板。

```bash
cd frontend
pnpm install        # 安装依赖

pnpm dev            # 开发模式（http://localhost:5173，Vite 代理转发到后端）
pnpm build          # 生产构建（产物在 frontend/dist）
```

**部署方式**：`pnpm build` 后，构建产物 `frontend/dist` 由**网关服务（8080）**挂载托管，浏览器访问 `http://127.0.0.1:8080/` 即为主界面（Docker 部署时由网关容器 volume 挂载，路径 `GATEWAY_DIST_DIR=/app/frontend/dist`）。

> 环境差异：生产构建时前端统一请求网关 `http://<host>:8080/api/*`（路径前缀见 `frontend/src/api.ts`）；开发模式走 Vite 代理将 `/api/*` 转发到网关 8080。所有后端 API 均需经网关统一入口，跨域（CORS）由网关统一开放。

## 目录结构

```
shopkeeper-think-tank/
├── packages/common/            # 公共底座 shopkeeper_common（配置/鉴权/异常/响应）
├── services/                   # 五个业务服务（独立模块）
│   ├── gateway/                #   shopkeeper_gateway   网关统一入口（8080）
│   ├── auth/                   #   shopkeeper_auth      认证（8083）
│   ├── user/                   #   shopkeeper_user      用户（8084）
│   ├── knowledge/              #   shopkeeper_knowledge 知识导入（8081）
│   └── query/                  #   shopkeeper_query     问答（8082）
├── frontend/                   # Vite + React 19 + TS 前端（pnpm）
├── deploy/                     # Dockerfile / compose.yml / .env.example
├── scripts/                    # deploy.py / deploy.bat / start_all.py
├── test/                       # 根级 e2e（test_09 / test_10）
├── .github/workflows/          # ci.yml / cd.yml
├── pyproject.toml              # uv workspace 根配置
└── run.bat                     # 一键启动/停止（合并原 start/stop）
```

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

