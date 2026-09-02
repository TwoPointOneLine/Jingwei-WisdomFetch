# 贡献指南

感谢参与精卫（Jingwei WisdomFetch）的开发。本文说明环境准备、日常命令与提交规范。

## 1. 仓库结构（先读这个，避免踩路径坑）

本仓库是 monorepo，存在**两个根**，务必区分：

| 名称 | 实际路径 | 用途 |
|---|---|---|
| **仓库根** | `Jingwei-WisdomFetch/` | `.env` 在此；`deploy/`、`docs/`、`scripts/`、`var/` |
| **Python 工程根** | `Jingwei-WisdomFetch/backend/` | uv workspace 根；`logs/`、`output/` 曾在此（现已外移到 `var/`） |

> ⚠️ **所有 `uv` / `pytest` / `ruff` 命令必须在 `backend/` 下执行**。
> 仓库根的 `pyproject.toml` 仅作 monorepo 标记（`[tool.uv] package = false`），不是 workspace 根。
> 在仓库根执行 `uv run pytest` 会失败。
>
> 推荐用统一入口 [`scripts/jingwei.ps1`](./scripts/jingwei.ps1)，它已封装目录切换。

## 2. 环境准备

```bash
# 后端（Python 3.11 + uv 0.7.0）
cd backend
uv sync --all-packages

# 前端（Node 20 + pnpm）
corepack enable
pnpm --dir frontend install

# 配置：复制模板为【仓库根】.env 并填入真实值
cp deploy/env/.env.example .env        # Linux
copy deploy\env\.env.example .env      # Windows
```

> `.env` 唯一位置是**仓库根**。放到 `deploy/.env` 或 `backend/.env` 都不会生效
> （compose 通过 `env_file: [../.env]` 引用）。
> 必填：`OPENAI_API_KEY`、`BGE_M3_PATH` / `BGE_RERANKER_LARGE`。

本地基础设施（Milvus / MongoDB / MinIO）：

```bash
docker compose -f deploy/docker-compose.yml up -d
```

## 3. 常用命令

### 统一入口（推荐）

```powershell
.\scripts\jingwei.ps1 help      # 查看全部命令
.\scripts\jingwei.ps1 dev       # 启动后端五服务
.\scripts\jingwei.ps1 test      # 后端测试
.\scripts\jingwei.ps1 lint      # 后端 lint
.\scripts\jingwei.ps1 up        # 容器编排启动
```

### 原生命令

```bash
# 后端（注意：在 backend/ 下执行）
cd backend
uv run ruff check packages services
uv run pytest packages/common/tests services/*/tests -q
uv lock --check
uv run python scripts/start_all.py --with-infra   # 或 run.bat

# 前端
pnpm --dir frontend dev
pnpm --dir frontend build

# 容器（注意：在仓库根执行，构建上下文 = 仓库根）
docker compose -f deploy/compose.yml up -d --build
docker compose -f deploy/compose.yml config --quiet     # 校验编排
```

## 4. 提交前检查（必须全绿）

```bash
cd backend && uv run ruff check packages services && uv run pytest ... -q
cd .. && docker compose -f deploy/compose.yml config --quiet
```

CI（`.github/workflows/ci.yml`）会执行同样内容：

- `uv lock --check` 校验 `backend/uv.lock` 与 pyproject 一致
- `ruff` 检查 `packages` 与 `services`
- `pytest` 运行全部测试
- `uv build` 构建六个包（common + 五服务）
- 前端 `pnpm lint` + `build`

## 5. 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat(query): 增加 HyDE 检索
fix(auth): 修正 token 过期判断
chore(root): 收敛环境变量模板
docs(backend): 补充会话隔离说明
refactor(common): 拆分 PROJECT_ROOT 与 REPO_ROOT
```

常用类型：`feat` / `fix` / `docs` / `refactor` / `chore` / `test` / `perf`。

> 提交信息会进入 CHANGELOG（见 `CHANGELOG.md`），请保证 type/scope 准确，便于自动归类。

## 6. 分支保护与评审（阶段5 · 9.4）

主分支 `main`（与 `master` 同步）启用以下保护规则（需在 GitHub 仓库 Settings 配置）：

1. **禁止直接 push**：所有改动经 PR 合入，PR 至少 1 名 reviewer 批准。
2. **必过检查**：`ci.yml` 的 `lint` / `test` / `layout` / `frontend` / `package` / `secret-scan` 全绿方可合并。
3. **双审批**：涉及安全（鉴权/网关）、部署（`deploy/`、`compose*.yml`、`Dockerfile`）或 `common` 公共底座的改动，需额外一名 `core-maintainers` 成员批准（依据 `.github/CODEOWNERS`）。
4. **线性历史**：启用 Squash merge 或 rebase，保持主线整洁可回溯。
5. **变更关联 Issue**：功能/修复类 PR 必须在描述中关联需求或缺陷编号。

PR 提交请使用模板（`.github/pull_request_template.md`），逐项勾选自测、安全与审查要求。

## 7. 密钥与合规红线（阶段5 · 9.2）

- **禁止明文凭据入库**：`.env` 已被 gitignore；模板仅留占位符（`.env.example` / `.env.prod.example`）。
- **CI 强制 gitleaks 全历史扫描**：任何疑似泄露会阻断合并；本地可用 `pre-commit run --hook-stage manual gitleaks` 预检。
- **部署前强口令断言**：`deploy.py check_env()` 会拒绝 `.env` 中的弱口令/占位符（如 `shopkeeper123`、`your_*`），避免生产用默认口令启动。
- **供应链审计**：CI 的 `dependency-audit` job 对 Python（`pip-audit`）与前端（`pnpm audit`）做开源依赖漏洞扫描，观察期不阻断，待清零后转 required。
- **生产环境**：使用 `deploy/compose.prod.yml` 覆盖，凭据从 `.env.prod` 读取，且业务服务端口不对外暴露（零信任内网）。


`CHANGELOG.md` 建议由 `git-cliff` 从提交记录自动生成，勿手工维护。

## 6. 改动高风险位置时的注意事项

| 改动位置 | 需同步检查 |
|---|---|
| `deploy/docker/*.Dockerfile` | `deploy/compose.yml` 的 `build.context`（须为 `..`，即仓库根）与 `cd.yml` 的 `-f` 路径 |
| 新增/修改 COPY 路径 | Dockerfile 元数据段必须带 `README.md`（hatchling editable 构建会校验 `readme`） |
| `.dockerignore` | 只在**构建上下文根**生效；现上下文为仓库根，故根目录那份生效 |
| `jingwei_common.config.common` | `PROJECT_ROOT`(backend) 与 `REPO_ROOT`(仓库根) 语义不同，勿混用 |
| 新增环境变量 | 必须同步加入 `deploy/env/.env.example`（唯一模板） |
| compose 网络名 / 数据卷 | 网络名 `shopkeeper` 为跨服务依赖，勿改；改编排文件名会导致容器失管 |

## 7. 分支与评审

- 当前主干：`master`（CI 同时兼容 `main`）
- 提交流程：开分支 → PR → CI 全绿 → 评审通过 → 合入
- PR 描述请说明：是否改动 Dockerfile / compose / CI、是否涉及数据卷、回滚方式

## 8. 不要提交

- 真实 `.env`（已在 `.gitignore`）
- `var/`（运行期日志与解析输出）
- `backend/logs/`、`backend/output/`（历史遗留，正迁移到 `var/`）
- 大体积二进制资源（前端 logo 请放 `src/assets/`，勿放 `public/`——后者会原样复制进产物且不经 tree-shaking）
