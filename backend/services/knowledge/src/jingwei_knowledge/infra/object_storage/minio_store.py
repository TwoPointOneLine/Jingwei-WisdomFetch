"""
MinIO 对象存储封装（infra 层）。

复用 shared/clients/minio_client 单例，提供业务友好的上传/下载/预签名接口。
"""
from jingwei_common.clients.minio_client import minio_client


class MinioStore:
    """对象存储封装。"""

    def ensure_bucket(self, bucket: str | None = None) -> str:
        return minio_client.ensure_bucket(bucket)

    def upload_file(self, object_name: str, file_path: str, bucket: str | None = None) -> str:
        return minio_client.upload_file(object_name, file_path, bucket)

    def upload_bytes(self, object_name: str, data: bytes, bucket: str | None = None) -> str:
        return minio_client.upload_data(object_name, data, bucket)

    def download_bytes(self, object_name: str, bucket: str | None = None) -> bytes:
        return minio_client.get_object(object_name, bucket)

    def remove(self, object_name: str, bucket: str | None = None):
        minio_client.remove_object(object_name, bucket)

    def presigned_url(self, object_name: str, bucket: str | None = None, expires: int = 3600) -> str:
        return minio_client.presigned_get(object_name, bucket, expires)


# 全局实例
object_storage = MinioStore()
