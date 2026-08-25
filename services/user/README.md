# shopkeeper-user

掌柜智库 用户服务（独立可部署模块）。

## 功能

- 用户档案 CRUD（MongoDB `user_profiles` 集合）
- 角色与权限管理（MVP：admin / member / guest）
- 角色→权限映射（admin 通配 `*`；member 含聊天/知识库读取；guest 仅聊天）
- 鉴权：所有业务接口需 `Authorization: Bearer <token>`（token 由 auth 服务签发，本地校验）

## 接口

| 方法 | 路径                        | 说明                                   | 权限             |
| ---- | --------------------------- | -------------------------------------- | ---------------- |
| POST | /user/profile               | 创建/初始化档案                        | 本人或 admin     |
| GET  | /user/profile/{username}    | 读取档案                               | 已登录           |
| PATCH| /user/profile/{username}    | 修改档案（nickname/organization 等）   | 本人或 admin     |
| GET  | /user/roles                 | 角色列表与权限说明                     | 已登录           |
| POST | /user/{username}/role       | 设置用户角色                           | 仅 admin         |
| GET  | /user/{username}/permissions| 查询用户权限                           | 已登录           |
| GET  | /health                     | 健康检查                               | -                |

## 运行

```bash
uv sync
uv run uvicorn shopkeeper_user.api.user_server.main:app --host 0.0.0.0 --port 8084
```

## 测试

```bash
uv run pytest -q
```
