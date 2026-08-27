"""
关键操作审计留痕（NFR-SEC-04）。

对「导入 / 查询 / 权限变更」等受监管动作，写入独立审计集合 audit_log，
供合规审计与问题追溯。审计写入失败不影响主业务流程（降级为本地日志）。
"""
from datetime import UTC, datetime

from jingwei_common.clients.mongo_client import mongo_client
from jingwei_common.constants import COLLECTION_AUDIT_LOG
from jingwei_common.logging import logger


def audit_log(
    action: str,
    actor: str = "",
    actor_role: str = "",
    detail: dict | None = None,
    status: str = "success",
    source: str = "",
) -> None:
    """记录一条审计事件。

    :param action: 动作类型，建议语义化，如 import_upload / import_retry /
                   query_chat / auth_login / user_role_change / session_delete 等。
    :param actor: 操作主体（用户名 / anon_id）。
    :param actor_role: 操作主体角色（admin / member / guest）。
    :param detail: 动作相关上下文（如 task_id、文件名、session_id）。
    :param status: success / failure。
    :param source: 调用来源服务标识（gateway / knowledge / query / auth / user）。
    """
    doc = {
        "action": action,
        "actor": actor,
        "actor_role": actor_role,
        "detail": detail or {},
        "status": status,
        "source": source,
        "ts": datetime.now(UTC),
    }
    try:
        coll = mongo_client.get_collection(COLLECTION_AUDIT_LOG)
        coll.insert_one(doc)
    except Exception as e:  # noqa: BLE001 — 审计不可阻塞主流程
        logger.warning(f"审计写入失败（已降级）: {e}")
