"""
Reranker（重排序）配置。

对应 .env 中 BGE-Reranker 本地重排序模型相关字段。
"""
from shopkeeper_common.config.common import env_bool, env_str


class RerankerConfig:
    # 本地模型目录绝对路径
    bge_reranker_large: str = env_str("BGE_RERANKER_LARGE", "")
    # 推理设备：cpu / cuda
    bge_reranker_device: str = env_str("BGE_RERANKER_DEVICE", "cpu")
    # 是否使用半精度（fp16）加速
    bge_reranker_fp16: bool = env_bool("BGE_RERANKER_FP16", False)


reranker_config = RerankerConfig()
