"""
MinIO 对象存储配置。

对应 .env 中对象存储相关字段。
本地直接运行用 localhost；Docker 容器内用 object-storage。
"""
from shopkeeper_common.config.common import env_bool, env_str


class MinioConfig:
    # 服务地址（host:port）
    endpoint: str = env_str("MINIO_ENDPOINT", "localhost:9000")
    access_key: str = env_str("MINIO_ACCESS_KEY", "")
    secret_key: str = env_str("MINIO_SECRET_KEY", "")
    # 默认桶名
    bucket: str = env_str("MINIO_BUCKET", "shopkeeper")
    # 是否使用 HTTPS
    secure: bool = env_bool("MINIO_SECURE", False)

    @property
    def host(self) -> str:
        return self.endpoint.split(":")[0] if self.endpoint else ""

    @property
    def port(self) -> int:
        parts = self.endpoint.split(":")
        return int(parts[1]) if len(parts) > 1 else 9000


minio_config = MinioConfig()
