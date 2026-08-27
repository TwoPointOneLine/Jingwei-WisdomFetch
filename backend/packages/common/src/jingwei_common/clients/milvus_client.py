"""
Milvus 底层客户端（单例）。

封装 MilvusClient 的创建与连接，业务/infra 层统一从这里取用，
避免重复建立连接。连接信息来自 milvus_config。
"""
from pymilvus import MilvusClient

from jingwei_common.config.milvus_config import milvus_config
from jingwei_common.logging import logger


class MilvusClientWrapper:
    """Milvus 客户端封装（懒加载单例）。"""

    _instance: "MilvusClientWrapper | None" = None
    _client: "MilvusClient | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> MilvusClient:
        """返回已连接的 MilvusClient，首次访问时建立连接。"""
        if self._client is None:
            logger.info(f"连接 Milvus: {milvus_config.milvus_url}")
            self._client = MilvusClient(uri=milvus_config.milvus_url)
        return self._client

    def has_collection(self, name: str) -> bool:
        return self.client.has_collection(name)

    def list_collections(self):
        return self.client.list_collections()

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None


# 全局单例
milvus_client = MilvusClientWrapper()
