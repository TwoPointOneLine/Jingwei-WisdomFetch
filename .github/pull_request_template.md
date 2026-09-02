<!-- 阶段5 · 9.4 评审可追溯：PR 模板 -->
<!-- 提交前请确认以下清单，并删除不相关项。 -->

## 变更说明
<!-- 简述本次 PR 的目的与核心改动，关联的需求/Issue 编号。 -->

## 变更类型
<!-- 勾选其一，关联 Conventional Commits 前缀（commit 须以 feat:/fix:/refactor:/docs:/chore: 等开头） -->
- [ ] feat: 新功能
- [ ] fix: Bug 修复
- [ ] refactor: 重构（无功能变化）
- [ ] docs: 文档
- [ ] chore: 构建/依赖/工具链
- [ ] perf: 性能
- [ ] test: 测试

## 影响范围
<!-- 列出受影响的服务/模块/配置；跨服务改动需注明兼容性与回滚方案。 -->
- 服务/模块：
- 配置/环境变量：
- 数据迁移需求：是 / 否

## 自测与验证
<!-- 说明本地/CI 已通过的验证；涉及部署的需贴出 compose config 结果。 -->
- [ ] `uv run ruff check` 通过
- [ ] `uv run pytest` 通过
- [ ] `python scripts/checks/run_all.py` 通过
- [ ] （部署相关）`docker compose -f deploy/compose.yml config` 通过

## 安全与合规
- [ ] 无明文密钥/凭据提交（gitleaks 全绿）
- [ ] 新增依赖已通过供应链审计（pip-audit / pnpm audit）
- [ ] 生产相关改动同步更新了 `deploy/env/.env.prod.example` 与 `compose.prod.yml`

## 审查要求
<!-- 根据 CODEOWNERS，下列路径变更需要指定 Reviewer -->
- Reviewer：@
- 是否需双人审批（安全/网关/部署）：是 / 否
