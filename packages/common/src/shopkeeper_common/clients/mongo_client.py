"""
MongoDB 底层客户端（单例）。

封装 pymongo MongoClient 的创建与连接，提供数据库访问入口。
连接信息来自 .env 中的 MONGO_URL / MONGO_DB_NAME。
"""
from pymongo import MongoClient
from pymongo.database import Database

from shopkeeper_common.config.common import env_str
from shopkeeper_common.logging import logger

MONGO_URL = env_str("MONGO_URL", "mongodb://127.0.0.1:27017")
MONGO_DB_NAME = env_str("MONGO_DB_NAME", "enterprise_rag")


class MongoClientWrapper:
    """MongoDB 客户端封装（懒加载单例）。"""

    _instance: "MongoClientWrapper | None" = None
    _client: "MongoClient | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            logger.info(f"连接 MongoDB: {MONGO_URL}")
            self._client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        return self._client

    @property
    def db(self) -> Database:
        return self.client[MONGO_DB_NAME]

    def get_collection(self, name: str):
        return self.db[name]

    def ping(self) -> bool:
        self.client.admin.command("ping")
        return True

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None


# 全局单例
mongo_client = MongoClientWrapper()
