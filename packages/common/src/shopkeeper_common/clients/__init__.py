"""基础客户端（懒加载单例）。

约定：业务代码不允许直接访问本包底层实现之外的能力，
统一通过本包导出的单例使用。
"""
from shopkeeper_common.clients.milvus_client import (
    MilvusClientWrapper,
    milvus_client,
)
from shopkeeper_common.clients.minio_client import (
    MinioClientWrapper,
    minio_client,
)
from shopkeeper_common.clients.mongo_client import (
    MONGO_DB_NAME,
    MONGO_URL,
    MongoClientWrapper,
    mongo_client,
)
from shopkeeper_common.clients.mongo_history_utils import (
    MESSAGE_COLLECTION,
    SESSION_COLLECTION,
    append_message,
    clear_session,
    create_session_if_not_exists,
    get_history,
    list_sessions,
    rename_session,
    update_session_meta,
)

__all__ = [
    "MongoClientWrapper",
    "mongo_client",
    "MONGO_URL",
    "MONGO_DB_NAME",
    "MilvusClientWrapper",
    "milvus_client",
    "MinioClientWrapper",
    "minio_client",
    "SESSION_COLLECTION",
    "MESSAGE_COLLECTION",
    "create_session_if_not_exists",
    "append_message",
    "get_history",
    "clear_session",
    "update_session_meta",
    "list_sessions",
    "rename_session",
]
