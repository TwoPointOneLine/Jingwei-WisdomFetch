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
COLLECTION_CHAT_FEEDBACK = "chat_feedback"
COLLECTION_AUDIT_LOG = "audit_log"  # NFR-SEC-04：关键操作审计留痕集合
COLLECTION_KNOWLEDGE_ITEMS = "knowledge_items"  # 资料级元信息（owner/visibility），供隔离与检索过滤
COLLECTION_KNOWLEDGE_BASES = "knowledge_bases"  # 知识库（逻辑库）元信息，用户自建 + 默认库

# ── 知识库（逻辑库）──────────────────────────────────────────────
# 逻辑库：同一 Milvus 集合内以 kb_name 字段区分，不单独建集合。
DEFAULT_KB = "default"  # 共享默认知识库（历史兼容，已被每用户默认库取代）
# 每用户默认知识库：以 default@<username> 命名，owner 为该用户，确保人人有独立默认库
KB_DEFAULT_PREFIX = "default@"
KB_NAME_MAXLEN = 64  # 库名最大长度

# ── 资料可见性（多级隔离）─────────────────────────────────────
# private：仅 owner 本人可见/可检索
# team   ：同团队成员（team_id 一致）可见/可检索（在「个人」之上增加团队空间）
# shared ：全员可见/可检索（进入统一共享检索池）
VIS_PRIVATE = "private"
VIS_TEAM = "team"
VIS_SHARED = "shared"
VIS_ALL = (VIS_PRIVATE, VIS_TEAM, VIS_SHARED)

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

# ── 团队概念 ──────────────────────────────────────────────────
# 用户归属某个团队（team_id），资料可设为 team（团队可见）。
# team_id 为空表示未加入任何团队（team 资料对其退化为仅 owner 可见）。
COLLECTION_TEAMS = "teams"  # 团队元信息集合（team_id -> {name, ...}）
