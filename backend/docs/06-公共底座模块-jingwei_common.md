# 公共底座模块 · jingwei_common

> 被所有业务服务依赖的共享库（`backend/packages/common`），不独立暴露。
> 代码：`backend/packages/common/src/jingwei_common/`

## 1. 职责

沉淀跨服务复用的能力，避免重复实现：AI 推理、客户端封装、配置、Web 基础、日志、工具。

## 2. 子包一览

### 2.1 `ai/` — AI 推理能力
| 模块 | 职责 |
|---|---|
| `chat.py` / `providers.py` | LLM 对话客户端（`llm_provider.chat(model=...)`），支持本地/百炼/DashScope，含 `LLM_MOCK` 模式 |
| `embedding.py` | BGE-M3 向量化（本地离线），供知识构建与检索 |
| `reranker.py` | BGE-Reranker 重排，供问答 RAG 链 |

### 2.2 `auth/` — 鉴权
- `authz.py`：Token 签发/校验、`get_user_role`、`require_role`（本地校验，免 HTTP，网关/用户/问答服务共用）。
- 常量见 `constants.py`：`ROLE_ADMIN`（`"*"`）/ `ROLE_MEMBER` / `ROLE_GUEST`、`COLLECTION_USER_PROFILES`。

### 2.3 `clients/` — 基础设施客户端
| 类 | 职责 |
|---|---|
| `milvus_client.MilvusClientWrapper` | 向量库读写（`insert` / `search`），集合由 `milvus_config` 定义 |
| `minio_client.MinioClientWrapper` | 对象存储（`upload_file` / `upload_data` / `get_object` / `presigned_get`），默认桶 `jingwei` |
| `mongo_client` | MongoDB 连接（`get_collection`） |
| `mongo_history_utils` | 会话历史 CRUD（`create_session_if_not_exists` / `append_message` / `get_history` / `clear_session` / `list_sessions` / `rename_session` / `get_session_meta` / `reassign_session` / `claim_guest_sessions`） |

### 2.4 `config/` — 配置分层
- 原子配置单例：`lm_config` / `embedding_config` / `milvus_config` / `minio_config` / `reranker_config` / `mineru_config` / `mcp_config` / `settings`。
- 聚合门面：`infra_config`（`providers.InfraConfig`），业务统一访问入口。
- 环境变量根：`JINGWEI_ROOT`。

### 2.5 `web/` — Web 基础
- `errors.py`：`ApiError` 及子类（`ForbiddenError` / `UnauthorizedError` / `NotFoundError` / `BadRequestError` / `ServiceError`），各服务注册异常处理器映射 HTTP。
- `response.py`：`ApiResponse` / `ok` / `fail`，统一 `{ code, message, data }`。
- `sse_utils.py`：`SSEEvent` / `create_sse_queue` / `get_sse_queue` / `push_to_session` / `sse_generator`，问答流式核心。
- `task_utils.py`：节点级任务进度（`add_running_task` / `add_done_task` / `update_task_status` / `get_task_status`），知识构建进度可视化依赖。

### 2.6 `logging/` — 统一日志
- `logger` / `step_log` / `node_log`：结构化步骤与节点日志（导入链/查询链节点统一 `@node_log` 记录）。

### 2.7 `utils/` — 工具
- `common_utils`：`chunk_text` / `clean_text` / `md5` / `safe_get`。
- `path_utils`：`ensure_dir` / `file_ext` / `is_pdf` / `temp_path` / `unique_filename`。
- `prompt_utils`：`load_prompt`（加载提示词模板）。

## 3. 设计要点

- **服务间鉴权零网络开销**：共用 `jingwei_common.auth`，本地校验 token/角色。
- **统一错误与响应**：所有服务复用 `web.errors` / `web.response`，前端一致解析。
- **配置集中**：业务不直接读环境变量，统一经 `config` 单例/门面。
- **可观测**：导入链与查询链节点进度、步骤日志统一经 `task_utils` / `logging` 暴露。

## 4. 依赖关系

```
jingwei_gateway ─┐
jingwei_auth ───┤
jingwei_user ───┼─> jingwei_common (ai/auth/clients/config/web/logging/utils)
jingwei_knowledge ─┤
jingwei_query ──┘
```
