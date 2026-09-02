# 更新日志

本项目的所有重要变更记录在此。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 建议后续改用 `git-cliff` 从 [Conventional Commits](https://www.conventionalcommits.org/)
> 自动生成，避免手工维护产生遗漏。

## [未发布]

### Added

- 仓库级统一入口 `scripts/jingwei.ps1`（dev / web / test / lint / lock / build / up / down / ps / health / logs）
- 文档唯一根 `docs/`，含 `docs/README.md` 索引、`docs/product/`（产品/需求/架构）、`docs/backend/`（模块文档）
- 根目录元文件 `CONTRIBUTING.md`、`CHANGELOG.md`
- 日志轮转压缩（`compression="zip"`），避免磁盘被日志占满
- 环境变量 `JINGWEI_LOG_DIR` / `JINGWEI_OUTPUT_DIR`，支持产物目录覆盖（默认 `<仓库根>/var/log`、`var/output`）

### Changed

- **文档归位**：`docs/00-02*` → `docs/product/`；`backend/docs/*` → `docs/backend/`。`backend/README.md` 保留为导航页
- **脚本分层**：诊断脚本移入 `backend/scripts/debug/`；删除与 `run.bat` 重复的 `run_backend.bat`
- **构建上下文提升为仓库根**（阶段 3 方案 B）：Dockerfile 由 `backend/deploy/` 移入 `deploy/docker/`，COPY 路径加 `backend/` 前缀。构建上下文 1309 MiB → 2.3 MiB
- **产物目录外移**：日志与解析输出由 `backend/logs`、`backend/output` 改为 `<仓库根>/var/log`、`var/output`（已 gitignore）
- **`.dockerignore` 改由根目录生效**（随构建上下文提升），并排除 `frontend/`（后端镜像不需要）

### Fixed

- **CI 全线失效**：lint/test/package 三个 job 缺 `working-directory: backend`，在仓库根执行必挂；触发分支 `main` 与实际 `master` 不符导致 push 不触发
- **CD 构建断链**：`cd.yml` 引用的 `deploy/docker/*.Dockerfile` 不存在，且 context 与 COPY 路径不匹配；另补前端构建 job
- **镜像构建失败**：Dockerfile 元数据段未 COPY 各包 `README.md`，hatchling editable 构建报 `Readme file does not exist`（`uv build` 不校验此字段，故本地易漏）
- **env 模板重复键**：`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` 各定义两次，dotenv 后者覆盖，实际生效的是占位值，按模板复制后 MinIO 必然连不上
- **`.env` 加载静默失效**：`PROJECT_ROOT` 实为 `backend/`，靠 `parent` 兜底才读到仓库根 `.env`；已拆分 `PROJECT_ROOT` 与 `REPO_ROOT`，缺失时告警
- **`start_all.py` 只读 `backend/.env`**：端口等配置会回退默认值；改为复用公共底座配置加载
- **会话归属实现落后于契约**：`list_sessions` 缺 `anon_id`、`reassign_session` 未清 `anon_id` 且无守卫、`get_history` 取最早 N 条而非最近
- **`uv build` 失败**：`packages/common` 的 `force-include` 与 `packages` 重复包含 resources，hatchling 报同名路径冲突
- **compose 挂载路径基准错误**：`./frontend/dist` 实为 `deploy/frontend/dist`，已改为 `../frontend/dist`
- **`deploy.py` 路径基准错误**：`ROOT = parents[1]` 指向 `backend/`，导致 `.env` 检查与前端构建全部找错位置（该脚本此前实际不可用）
- **前端产物冗余**：`public/logo/` 与 `src/assets/` 字节级重复且零引用，删除后 `dist` 由 7.48 MiB 降至 3.29 MiB

### Removed

- `deploy/.env.example` 与 `backend/services/*/.env.example`（6 处模板合并为唯一的 `deploy/env/.env.example`）
- `backend/run_backend.bat`（与 `run.bat` 重复）
- `scripts/_kbfix_debug.py`、`scripts/_kbfix_test.ps1`（一次性排查残留，含硬编码路径与测试账号）
- `frontend/public/logo/`（与 `src/assets/` 重复且未被引用）
- 根级 `uv.lock`（uv virtual root 生成的 139B 虚锁，与 `backend/uv.lock` 同名易误判；已 gitignore）

## [0.1.0]

初始版本，含网关 / 认证 / 用户 / 知识导入 / 问答五服务与前端。

- `fb94937` refactor: 重命名项目为 jingwei 并迁移到 backend 目录
- `dc4c464` fix: 修复 query 服务 MongoDB 认证失败与日志 KeyError 崩溃
- `e6ef377` fix: 一键启动脚本改用 uv 环境并修复日志编码/进程树清理
- `915c536` feat: 增强后端一键启动（--with-infra + 前台常驻 + 优雅停止）
- `a62b137` fix: 恢复误删的 run.bat 与 scripts/start_all.py
- `3441ec9` docs: 更新 README 与网关统一入口架构对齐
- `34a539c` init: 智能知识问答系统（多模块架构）
