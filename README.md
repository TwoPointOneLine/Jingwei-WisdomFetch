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

## 快速开始

```bash
# 1) 后端（uv workspace，含五大微服务 + 公共底座）
cd backend
uv sync                       # 安装依赖
.\run_backend.bat             # 一键拉起基础设施 + 五服务（Ctrl+C 停止）

# 2) 前端（pnpm）
pnpm --dir frontend install
pnpm --dir frontend dev

# 3) 容器化部署（编排在仓库根 deploy/，Dockerfile 在 backend/deploy/）
docker compose -f deploy/compose.yml up -d --build
```

## 快速入口

- **后端工程说明**：[`backend/README.md`](./backend/README.md) —— 环境、一键启动、Docker 部署、服务矩阵。
- **产品文档**：[`docs/00精卫金融知识库产品介绍.md`](./docs/00精卫金融知识库产品介绍.md)。
- **需求与架构**：[`docs/01…产品需求分析.md`](./docs/01精卫金融知识库产品需求分析.md) · [`docs/02…项目整体架构.md`](./docs/02精卫金融智能知识库项目整体架构.md)。

## 说明

- 仓库根 `pyproject.toml` 仅为 monorepo 标记，Python 依赖与构建以 `backend/` 为准。
- 产品定位、合规边界与品牌命名见 `docs/` 与 `backend/` 内对应文档。
