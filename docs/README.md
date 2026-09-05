# 文档索引

精卫（Jingwei WisdomFetch）文档唯一根目录。

> 2026-08-31 阶段 4 归位：此前文档分散在 `docs/`、`backend/docs/`、`backend/README.md` 三处，
> 现统一到本目录。`backend/README.md` 保留为后端导航页（20 行内的快速索引）。

## 目录结构

| 目录 | 内容 |
|---|---|
| [`product/`](./product) | 产品介绍 / 需求分析 / 整体架构 / **用户使用指南**（00~03） |
| [`backend/`](./backend) | 后端模块文档（总览 + 网关/认证/用户/知识构建/问答/公共底座） |
| [`deploy/`](./deploy) | 部署与运维说明（待补） |

## 推荐阅读顺序

1. [`product/00精卫金融知识库产品介绍.md`](./product/00精卫金融知识库产品介绍.md) —— 产品定位、功能全景、竞品对比
2. [`product/01精卫金融知识库产品需求分析.md`](./product/01精卫金融知识库产品需求分析.md) —— FR-* 功能需求编号（模块文档均按此编号对应）
3. [`product/02精卫金融知识库项目整体架构.md`](./product/02精卫金融知识库项目整体架构.md) —— 技术架构、服务拆分、数据模型
4. [`product/03精卫用户使用指南.md`](./product/03精卫用户使用指南.md) —— **终端用户手册**：登录、问答、知识库管理、FAQ
5. [`product/04精卫技术栈介绍.md`](./product/04精卫技术栈介绍.md) —— **技术栈总览**：后端/前端/检索/部署与 CI 选型与版本
4. [`backend/00-后端功能模块总览.md`](./backend/00-后端功能模块总览.md) —— 后端服务矩阵、功能编号与代码路径对照
5. 按需要阅读 `backend/01`~`06` 各模块文档

## 其他入口

- 仓库总览：[`../README.md`](../README.md)
- 后端快速索引：[`../backend/README.md`](../backend/README.md)
- 配置模板：[`../deploy/env/.env.example`](../deploy/env/.env.example)
