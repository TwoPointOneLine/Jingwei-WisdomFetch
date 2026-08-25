"""
MinIO 底层客户端（单例）。

封装 minio Client 的创建与连接，提供桶初始化与对象读写入口。
连接信息来自 minio_config。
"""
from minio import Minio

from shopkeeper_common.config.minio_config import minio_config
from shopkeeper_common.logging import logger


class MinioClientWrapper:
    """MinIO 客户端封装（懒加载单例）。"""

    _instance: "MinioClientWrapper | None" = None
    _client: "Minio | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> Minio:
        if self._client is None:
            logger.info(
                f"连接 MinIO: {minio_config.endpoint} (secure={minio_config.secure})"
            )
            self._client = Minio(
                endpoint=minio_config.endpoint,
                access_key=minio_config.access_key,
                secret_key=minio_config.secret_key,
                secure=minio_config.secure,
            )
        return self._client

    def ensure_bucket(self, bucket: str | None = None) -> str:
        """确保桶存在，不存在则创建，返回桶名。"""
        name = bucket or minio_config.bucket
        found = self.client.bucket_exists(name)
        if not found:
            logger.info(f"创建 MinIO 桶: {name}")
            self.client.make_bucket(name)
        return name

    def upload_file(self, object_name: str, file_path: str, bucket: str | None = None) -> str:
        bucket = self.ensure_bucket(bucket)
        self.client.fput_object(bucket, object_name, file_path)
        return f"{bucket}/{object_name}"

    def upload_data(self, object_name: str, data: bytes, bucket: str | None = None) -> str:
        bucket = self.ensure_bucket(bucket)
        from io import BytesIO

        self.client.put_object(bucket, object_name, BytesIO(data), length=len(data))
        return f"{bucket}/{object_name}"

    def get_object(self, object_name: str, bucket: str | None = None) -> bytes:
        bucket = bucket or minio_config.bucket
        from io import BytesIO

        resp = self.client.get_object(bucket, object_name)
        buf = BytesIO()
        for chunk in resp.stream(32 * 1024):
            buf.write(chunk)
        resp.close()
        resp.release_conn()
        return buf.getvalue()

    def remove_object(self, object_name: str, bucket: str | None = None):
        bucket = bucket or minio_config.bucket
        self.client.remove_object(bucket, object_name)

    def presigned_get(self, object_name: str, bucket: str | None = None, expires=3600) -> str:
        bucket = bucket or minio_config.bucket
        return self.client.presigned_get_object(bucket, object_name, expires)


# 全局单例
minio_client = MinioClientWrapper()
