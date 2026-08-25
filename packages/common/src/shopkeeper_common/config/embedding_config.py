"""
Embedding（向量化）配置。

对应 .env 中 BGE-M3 本地向量模型相关字段。
"""
import os

from shopkeeper_common.config.common import env_bool, env_int, env_str


class EmbeddingConfig:
    # 模型来源：local=本地模型目录；留空则回退远程 "BAAI/bge-m3"
    bge_m3: str = env_str("BGE_M3", "local")
    # 本地模型目录绝对路径，留空则回退远程拉取
    _raw_bge_m3_path: str = env_str("BGE_M3_PATH", "")

    @property
    def bge_m3_path(self) -> str:
        """规范化为系统原生路径分隔符。

        注意：Windows 下 FlagEmbedding/transformers 需要原生反斜杠绝对路径
        （如 D:\\ai_models\\...），若统一为正斜杠会被误判为 HuggingFace repo id。
        因此用 os.path.normpath 而非简单替换为正斜杠。
        """
        return os.path.normpath(self._raw_bge_m3_path) if self._raw_bge_m3_path else ""
    # 推理设备：cpu / cuda
    bge_device: str = env_str("BGE_DEVICE", "cpu")
    # 是否使用半精度（fp16）加速
    bge_fp16: bool = env_bool("BGE_FP16", False)
    # 向量维度（BGE-M3 默认 1024）
    embedding_dim: int = env_int("EMBEDDING_DIM", 1024)


embedding_config = EmbeddingConfig()
