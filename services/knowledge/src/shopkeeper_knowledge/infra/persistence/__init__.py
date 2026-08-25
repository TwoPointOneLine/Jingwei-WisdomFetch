"""
infra/persistence 统一导出（knowledge 域仅使用 mongo_store）。
"""
from shopkeeper_knowledge.infra.persistence.mongo_store import MongoStore, persistence

__all__ = ["MongoStore", "persistence"]
