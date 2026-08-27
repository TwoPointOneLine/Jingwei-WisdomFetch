# 精卫 (Jingwei WisdomFetch)

> **衔海求知，汇流成库。每一问，都有来处。**
>
> *Fetching knowledge from the sea of finance.*

**精卫（Jingwei WisdomFetch，缩写 JWF）** 是一款面向普通用户的**金融智能知识库系统**——基于 FastAPI + LangGraph + Milvus + MongoDB + MinIO 构建的企业级私有知识库智能问答系统（RAG）。

用户无需知道资料存放位置，也无需手动翻阅大量 PDF、公告、产品说明书或问答文档——只需像聊天一样输入问题，精卫即可从已导入的金融知识库中检索相关内容，并生成清晰、可追溯的回答。

## 产品介绍

### 产品定位

**金融知识查询与资料理解工具**：

- 不提供个性化投资建议；
- 不承诺收益；
- 不替代正式产品文件、监管文件或人工专业判断。

### 命名由来

"精卫"源自《山海经》"精卫填海"典故——炎帝之女女娃溺于东海，化为精卫鸟，日复一日衔西山之木石以填沧海。其精神内核为**坚韧、执着、以小博大**。

| 神话元素 | 产品映射 | 寓意解读 |
| :--- | :--- | :--- |
| 沧海 | 浩如烟海的金融文档（PDF、公告、研报、说明书） | 信息之海，用户难以独自遍历 |
| 西山木石 | 散落在各文件中的知识碎片 | 每一条产品条款、每一段风险提示 |
| 精卫衔石 | 系统的检索与抽取能力 | 从海量资料中精准衔取对用户有价值的内容 |
| 填海 | 为用户筑起可理解的知识陆地 | 把晦涩的专业文档，变成人人可读的答案 |
| 日复一日 | 7×24 小时不间断服务 | 知识库持续积累，回答持续可追溯 |

### 目标用户与核心价值

**目标用户**：希望了解金融产品条款、风险等级、申赎规则的**普通投资者**；需要快速读懂公告、研报、政策文件的**金融从业者**；需要统一知识管理能力的**金融机构内部团队**。

**核心价值**：

1. **降低理解门槛**：用通俗语言解释专业条款与金融术语，让非专业用户也能读懂。
2. **答案有据可查**：每条回答尽量标注来源文件、产品名称、发布时间，做到可追溯。
3. **合规安全可靠**：不荐股、不承诺收益，风险提示严谨，无资料时不编造。
4. **对话式体验**：支持自然语言提问与多轮追问，像聊天一样查询资料。

### 功能体系

| 模块 | 命名 | 寓意 |
| :--- | :--- | :--- |
| 产品整体 | **精卫 · 金融知识库** | 主品牌 |
| 智能问答引擎 | **精卫问答** | 核心对话能力 |
| 文档导入与管理 | **精卫衔文** | "衔"取文档入库存 |
| 引用溯源展示 | **精卫引源** | 标注答案来源，可追溯 |
| 风险提示模块 | **精卫守正** | 守住合规边界，提示风险 |
| 公告/资讯解读 | **精卫读报** | 读透公告与研报 |
| 多轮对话能力 | **精卫追问** | 支持上下文连续提问 |
| 历史记录 | **精卫留痕** | 保留查询痕迹，便于复盘 |

**查询能力覆盖**：金融产品资料、产品说明书、产品风险揭示书；基金招募说明书、基金产品资料概要；理财产品说明书、业务流程说明；市场资讯、行业分析、宏观政策与研究资料；公司公告摘要、政策解读资料；金融术语解释、常见问题 FAQ、风险提示材料。

### 典型使用场景

| 场景 | 用户提问 | 系统返回 |
| :--- | :--- | :--- |
| 查询产品 | 帮我介绍一下 XX 基金 | 产品基本信息、投资方向、风险等级、费用/申赎规则、主要风险、来源文件 |
| 查询风险 | 这个理财产品有什么风险？ | 相关风险提示，并提醒本金亏损、收益波动、流动性限制、市场/信用风险等 |
| 查询概念 | 什么是净值型理财？ | 通俗概念解释 + 知识库注意事项 |
| 查询公告 | 这份公司公告主要讲了什么？ | 公告核心内容总结 + 公告名称、发布时间、来源文件 |
| 查询业务 | 基金赎回多久到账？ | 操作说明、到账时间、注意事项、来源信息 |
| 多轮追问 | 这个产品风险高吗？/ 适合稳健型用户吗？ | 结合上下文理解同一产品，继续基于知识库回答 |

### 知识库内容字段

知识库中每条内容建议包含以下字段：

```json
{
  "content": "正文内容",
  "content_type": "产品说明书 / 风险提示 / 公告摘要 / FAQ / 金融术语",
  "document_title": "资料名称",
  "product_name": "产品名称",
  "product_code": "产品代码",
  "institution_name": "机构名称",
  "risk_level": "风险等级",
  "industry": "行业分类",
  "market": "市场类型",
  "publish_date": "发布时间",
  "entry_name": "条目名称",
  "source_file": "来源文件名",
  "source_path": "来源路径或资源链接"
}
```

### 回答要求与合规边界

- **回答结构**：简要结论 → 主要内容 → 风险提示 → 注意事项 → 引用来源（资料名称、内容类型、产品名称/代码、发布时间、来源文件名）。
- **无资料不编造**：知识库未检索到足够信息时明确提示"查看正式产品文件、公告原文或咨询相关工作人员"，不编造数据、公告内容、产品条款或市场结论。
- **合规原则**：不提供投资建议、不承诺收益、风险提示谨慎（"金融产品存在风险""历史业绩不代表未来表现""投资需结合自身风险承受能力"）、不保证实时性（涉及最新行情/净值/公告时提示查看官方渠道）。
- **交互能力**：单轮问答、多轮追问（上下文理解）、流式输出、历史记录查看与重新提问、引用来源展示、异常提示。

### 品牌故事

> 东海浩瀚，文件如潮。
>
> 每一份产品说明书、每一纸公告、每一篇研报，都像散落在沧海中的木石——珍贵，却难以逐一拾起。
>
> **精卫**由此而生。
>
> 我们以 AI 为翼，以检索为喙，日复一日，从浩如烟海的资料中，为你衔来那一叶最相关的答案。
>
> 不编造，不承诺，只传递有据可依的金融知识。
>
> **衔海求知，汇流成库。每一问，都有来处。**

---

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

# 运行环境自检（执行后端测试套件，验证依赖与导入）
uv run pytest
```

## 配置

在**仓库根**创建 `.env` 并填入真实密钥与服务地址（应用运行时由 backend 服务从仓库根 `.env` 读取；compose 编排通过 `env_file: [../.env]` 引用仓库根 `.env`）。可参考各服务自带的模板：

```bash
# 仓库根 .env 参考 backend/services/{gateway,auth,user,knowledge,query}/.env.example
copy backend\services\gateway\.env.example .env
```

> 注：原 `deploy/.env.example` 已不存在，环境变量模板分散在各服务目录下。

## 一键启动（本地运行）

提供一键脚本，自动检查基础设施（Milvus / MongoDB / MinIO）连通性、并行拉起**网关 + 认证 + 用户 + 知识 + 问答五个服务**并等待健康：

```bash
# 最简一键（双击 backend/run_backend.bat）：自动拉起基础设施(docker compose) + 五大后端服务，前台常驻，Ctrl+C 停止
backend\run_backend.bat

# 或手动分步（在 backend/ 目录下）：
# 1) 先拉起基础设施（Docker，编排文件在仓库根 deploy/）
docker compose -f ..\deploy\docker-compose.yml up -d
# 2) 启动全部服务（前台常驻，Ctrl+C 停止）；--with-infra 可合并第 1 步
backend\run.bat
backend\run.bat --with-infra
uv run python scripts/start_all.py --with-infra

# 停止（按端口清理进程）
backend\run.bat --stop
uv run python scripts/start_all.py --stop

# 仅检查环境（不启动）
uv run python scripts/start_all.py --check
```

启动成功后，所有流量走**网关统一入口（8080）**：
- 前端主界面：http://127.0.0.1:8080/
- 网关 API 文档：http://127.0.0.1:8080/gateway/docs
- 各后端服务文档：http://127.0.0.1:8083/docs（认证）、http://127.0.0.1:8084/docs（用户）、http://127.0.0.1:8081/docs（知识导入）、http://127.0.0.1:8082/docs（问答）
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
jingwei-wisdom-fetch/                 # 仓库根
├── backend/                         # Python 工程根（uv workspace）
│   ├── packages/common/             #   公共底座 jingwei_common（配置/鉴权/异常/响应）
│   ├── services/                    #   五个业务服务（独立模块）
│   │   ├── gateway/                 #     jingwei_gateway   网关统一入口（8080）
│   │   ├── auth/                    #     jingwei_auth      认证（8083）
│   │   ├── user/                    #     jingwei_user      用户（8084）
│   │   ├── knowledge/               #     jingwei_knowledge 知识导入（8081）
│   │   └── query/                   #     jingwei_query     问答（8082）
│   ├── deploy/docker/               #   Dockerfile（uv 多阶段构建）
│   ├── scripts/                     #   deploy.py / deploy.bat / start_all.py
│   ├── pyproject.toml               #   uv workspace 根配置
│   ├── uv.lock
│   └── run.bat / run_backend.bat    # 一键启动/停止
├── deploy/                          # 仓库根：compose.yml / docker-compose.yml（基础设施编排）
├── frontend/                        # Vite + React 19 + TS 前端（pnpm）
└── docs/                            # 产品/需求/架构文档
```

## Docker 部署（阶段 5：全模块独立镜像 + 按需启停）

基础设施（etcd / Milvus / MongoDB / MinIO / Attu）与五个服务模块（网关/认证/用户/知识/问答）由 `deploy/compose.yml` 统一编排（`include` 合并同名目录下基础设施 `docker-compose.yml`），并支持一键部署脚本。

### 1. 一键部署（推荐）

```bash
# 在仓库根创建 .env（参考 backend/services/{gateway,auth,user,knowledge,query}/.env.example）
copy backend\services\gateway\.env.example .env

# 构建前端 + 五服务镜像并全部启动（依赖自动拉起，等待健康检查通过）
backend\scripts\deploy.bat up

# 按需启停：只启动网关与问答（依赖基础设施自动拉起）
backend\scripts\deploy.bat up --services gateway,query

# 健康检查 / 查看状态 / 停止 / 清数据
backend\scripts\deploy.bat health
backend\scripts\deploy.bat ps
backend\scripts\deploy.bat down
backend\scripts\deploy.bat down --volumes
backend\scripts\deploy.bat logs gateway
```

### 2. 手动 compose（等价）

```bash
# 构建镜像（前端 dist 由网关经 volume 挂载托管，需先构建前端：pnpm --dir frontend build）
# 注意：compose 编排在仓库根 deploy/，build context 指向 backend/
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

- **`.env`**：在仓库根创建（参考 `backend/services/*/.env.example`），填入 `OPENAI_API_KEY`、`BGE_MODELS_DIR`（本机模型根目录，挂载进知识/问答容器）等；`MONGO_DB_NAME` 为共享库名，勿改动。
- **镜像**：`backend/deploy/{gateway,auth,user,knowledge,query}.Dockerfile`（uv workspace 多阶段构建，build context 为 `../backend`，tag `jingwei-{module}:0.1.0`），镜像内置 `/health` 健康检查。
- **前端**：`pnpm --dir frontend build` 产出 `frontend/dist`，由网关容器挂载托管（`GATEWAY_DIST_DIR=/app/frontend/dist`）。
- **CI/CD**：`.github/workflows/ci.yml`（lint/测试/前端/打包）与 `cd.yml`（打 `v*` tag 推送五服务镜像到 GHCR）；CI 配置位于 `backend/.github/`（随 backend 工程根）。

> 注意：Milvus standalone 内部自带一个 MinIO（端口 9200/9201），与「外部对象存储 MinIO」（9000/9001）端口已错开，避免冲突。知识/问答镜像含 torch 等推理依赖，首次构建需拉取较大依赖。

