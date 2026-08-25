# shopkeeper-auth

掌柜智库 认证服务（独立可部署模块）。

## 功能

- 用户注册 / 登录 / 登出
- token 签发与校验（MongoDB `auth_tokens` 集合，本地校验）
- 注册时同步初始化 `user_profiles` 档案与默认角色（member）
- 引导管理员：环境变量 `AUTH_BOOTSTRAP_ADMIN=admin1,admin2`（逗号分隔），
  命中用户注册时角色为 admin

## 接口

| 方法 | 路径           | 说明                         |
| ---- | -------------- | ---------------------------- |
| POST | /auth/register | 注册（含角色初始化）         |
| POST | /auth/login    | 登录，返回 token             |
| GET  | /auth/me       | 校验 token，返回用户与角色   |
| POST | /auth/logout   | 注销 token                   |
| GET  | /health        | 健康检查                     |

## 运行

```bash
uv sync
uv run uvicorn shopkeeper_auth.api.auth_server.main:app --host 0.0.0.0 --port 8083
```

## 测试

```bash
uv run pytest -q
```
