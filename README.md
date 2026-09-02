# 精卫 · 金融智能知识库（Jingwei WisdomFetch / JWF）

> *Fetching knowledge from the sea of finance.*

企业级**私有化金融知识库智能问答系统**（RAG 架构），面向金融机构提供"不荐股、不承诺收益、答案可追溯"的知识查询与资料理解能力。

## 仓库结构（monorepo）

本仓库为聚合根，包含三个子工程：

| 目录 | 工程 | 说明 |
|---|---|---|
| [`backend/`](./backend) | Python（uv workspace） | 五大微服务 + 公共底座 `jingwei_common`，uv workspace 根在 `backend/pyproject.toml` |
| [`frontend/`](./frontend) | React + Vite + TS | 用户交互前端（pnpm 管理） |
| [`deploy/`](./deploy) | Docker 编排 | `compose.yml`（五服务）+ `docker-compose.yml`（基础设施） |
| [`docs/`](./docs) | 文档 | 产品介绍 / 需求分析 / 整体架构（00~02 递进） |

## 配置

仓库根 `.env` 是**唯一**配置来源，模板位于 [`deploy/env/.env.example`](./deploy/env/.env.example)：

```bash
# Windows
copy deploy\env\.env.example .env
# Linux
cp deploy/env/.env.example .env
```

> ⚠️ 位置必须是**仓库根**（compose 通过 `env_file: [../.env]` 引用）。
> 必填：`OPENAI_API_KEY`、`BGE_M3_PATH` / `BGE_RERANKER_LARGE`。
> 非本机部署前修改所有标注 `CHANGE_ME` 的口令。

## 快速开始

```bash
# 1) 后端（uv workspace，含五大微服务 + 公共底座）
cd backend
uv sync                       # 安装依赖
backend\run.bat               # 一键拉起五服务（Ctrl+C 停止，加 --with-infra 连基础设施）

# 2) 前端（pnpm）
pnpm --dir frontend install
pnpm --dir frontend dev

# 3) 容器化部署（编排与 Dockerfile 均在仓库根 deploy/）
docker compose -f deploy/compose.yml up -d --build
```

## 快速入口

- **后端工程说明**：[`backend/README.md`](./backend/README.md) —— 环境、一键启动、Docker 部署、服务矩阵。
- **文档索引**：[`docs/README.md`](./docs/README.md)
  - 产品：[`00 产品介绍`](./docs/product/00精卫金融知识库产品介绍.md) · [`01 需求分析`](./docs/product/01精卫金融知识库产品需求分析.md) · [`02 整体架构`](./docs/product/02精卫金融知识库项目整体架构.md)
  - 后端：[`00 模块总览`](./docs/backend/00-后端功能模块总览.md) · `01`~`06` 各模块文档（见 `docs/backend/`）

## 说明

- 仓库根 `pyproject.toml` 仅为 monorepo 标记（`[tool.uv] package = false`），Python 依赖与构建以 `backend/` 为准；`backend/uv.lock` 是真实依赖锁，根级 `uv.lock` 是 uv 生成的虚锁，已忽略。
- 所有 `uv` / `pytest` / `ruff` 命令请在 `backend/` 下执行（仓库根非 uv workspace 根）。
- 产品定位、合规边界与品牌命名见 `docs/` 与 `backend/` 内对应文档。
