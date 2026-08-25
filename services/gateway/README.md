# shopkeeper-gateway

掌柜智库 网关服务（统一入口，端口 8080）。

## 功能

- 路由转发：`/api/auth/*`→auth(8083)、`/api/user/*`→user(8084)、
  `/api/knowledge/*` 与 `/api/import/*`→knowledge(8081)、`/api/query/*`→query(8082)
- 统一鉴权前置：校验 `Authorization: Bearer <token>`（复用 `shopkeeper_common.auth` 本地校验）
  - `GATEWAY_AUTH_MODE=strict`：白名单外必须携带有效 token
  - `GATEWAY_AUTH_MODE=optional`（默认）：携带 token 必须有效；未携带放行（guest）
  - 白名单：`/api/auth/*` 注册/登录/me/登出、`/api/query/models`
  - SSE 端点免鉴权（EventSource 无法带 header），支持 `?token=` 兜底
- SSE 流式代理（逐块透传 `text/event-stream`）
- 限流：`GATEWAY_RATE_LIMIT`（每分钟每 IP 请求数，0=关闭）
- 访问日志（loguru）
- CORS（`CORS_ORIGINS`，默认 `*`）
- 静态资源托管：`frontend/dist`（存在时挂载；`GATEWAY_DIST_DIR` 可覆盖）
- 健康检查：`GET /health`

## 接口

| 方法 | 路径              | 说明                       |
| ---- | ----------------- | -------------------------- |
| GET  | /health           | 健康检查（含后端路由表）   |
| *    | /api/{service}/*  | 转发到对应后端服务         |
| GET  | /                 | 前端入口（dist 存在时）    |
| GET  | /assets/*         | 前端静态资源（dist 存在时）|

## 运行

```bash
uv sync
uv run uvicorn shopkeeper_gateway.api.gateway_server.main:app --host 0.0.0.0 --port 8080
```

## 测试

```bash
uv run pytest -q
```
