"""
infra/object_storage 统一导出。
"""
from shopkeeper_knowledge.infra.object_storage.minio_store import MinioStore, object_storage

__all__ = ["MinioStore", "object_storage"]
