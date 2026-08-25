"""
infra/persistence 统一导出。
"""
from shopkeeper_query.infra.persistence.history_repository import HistoryRepository, history_repo
from shopkeeper_query.infra.persistence.mongo_store import MongoStore, persistence

__all__ = ["MongoStore", "persistence", "HistoryRepository", "history_repo"]
