"""
MongoDB 持久化封装（infra 层）。

复用 shared/clients/mongo_client 单例，提供集合读写等便捷接口，
用于企业信息、导入记录、查询会话等结构化数据存储。
"""

from shopkeeper_common.clients.mongo_client import mongo_client


class MongoStore:
    """MongoDB 持久化封装。"""

    def get_collection(self, name: str):
        return mongo_client.get_collection(name)

    def insert_one(self, collection: str, doc: dict):
        return self.get_collection(collection).insert_one(doc)

    def find_one(self, collection: str, query: dict) -> dict | None:
        return self.get_collection(collection).find_one(query)

    def find(self, collection: str, query: dict | None = None, limit: int = 0) -> list[dict]:
        cursor = self.get_collection(collection).find(query or {})
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update_one(self, collection: str, query: dict, update: dict, upsert: bool = False):
        return self.get_collection(collection).update_one(query, update, upsert=upsert)

    def delete_many(self, collection: str, query: dict):
        return self.get_collection(collection).delete_many(query)


# 全局实例
persistence = MongoStore()
