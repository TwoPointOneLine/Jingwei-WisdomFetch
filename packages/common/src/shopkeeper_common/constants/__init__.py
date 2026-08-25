"""全局常量。

任务状态、SSE 事件、错误码、Mongo 集合名、角色定义等，
供所有服务模块共享引用，避免散落的魔法字符串。
"""

# ── 任务状态 ──────────────────────────────────────────────────
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

TASK_STATUS_ORDER = (
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)

# ── SSE 事件名 ────────────────────────────────────────────────
SSE_EVENT_READY = "ready"
SSE_EVENT_PROGRESS = "progress"
SSE_EVENT_DELTA = "delta"
SSE_EVENT_FINAL = "final"
SSE_EVENT_ERROR = "error"
# 内部哨兵事件：表示流结束
SSE_EVENT_CLOSE = "__close__"

SSE_ALL_EVENTS = (
    SSE_EVENT_READY,
    SSE_EVENT_PROGRESS,
    SSE_EVENT_DELTA,
    SSE_EVENT_FINAL,
    SSE_EVENT_ERROR,
    SSE_EVENT_CLOSE,
)

# ── 统一响应错误码（业务 code，HTTP 状态码另行映射）───────────
CODE_OK = 0
CODE_BAD_REQUEST = 400
CODE_UNAUTHORIZED = 401
CODE_FORBIDDEN = 403
CODE_NOT_FOUND = 404
CODE_SERVER_ERROR = 500

# ── MongoDB 集合名 ────────────────────────────────────────────
COLLECTION_USERS = "users"
COLLECTION_SESSIONS = "chat_sessions"
COLLECTION_MESSAGES = "chat_messages"
COLLECTION_USER_PROFILES = "user_profiles"
COLLECTION_AUTH_TOKENS = "auth_tokens"

# ── 角色定义 ──────────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_GUEST = "guest"

# MVP 角色 → 权限映射（admin 通配 *；供 user 服务返回与业务侧授权参考）
ROLE_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ADMIN: ["*"],
    ROLE_MEMBER: [
        "chat.query",
        "chat.session",
        "kb.read",
        "user.profile.read",
        "user.profile.self",
    ],
    ROLE_GUEST: ["chat.query", "user.profile.read"],
}

ALL_ROLES = (ROLE_ADMIN, ROLE_MEMBER, ROLE_GUEST)
