"""
MinerU PDF 解析服务配置。

对应 .env 中 MINERU_API_URL 字段。
"""
from shopkeeper_common.config.common import env_str


class MinerUConfig:
    # MinerU 解析服务 API 地址
    api_url: str = env_str("MINERU_API_URL", "")


mineru_config = MinerUConfig()
