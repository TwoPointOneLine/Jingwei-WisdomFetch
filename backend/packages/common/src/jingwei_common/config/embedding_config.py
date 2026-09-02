"""
Embedding（向量化）配置。

对应 .env 中 BGE-M3 本地向量模型相关字段。
"""
import os

from jingwei_common.config.common import env_bool, env_int, env_str


class EmbeddingConfig:
    # 模型来源：local=本地 FlagEmbedding 权重；ollama=本地 Ollama 服务
    # （BGE-M3 在 Ollama 中以 embedding 类型提供，仅返回稠密向量）。
    bge_m3_provider: str = env_str("BGE_M3", "local")
    # 本地模型目录绝对路径（仅 local 模式使用），留空则回退远程拉取
    _raw_bge_m3_path: str = env_str("BGE_M3_PATH", "")

    @property
    def bge_m3_path(self) -> str:
        """规范化为系统原生路径分隔符。

        注意：Windows 下 FlagEmbedding/transformers 需要原生反斜杠绝对路径
        （如 D:\\ai_models\\...），若统一为正斜杠会被误判为 HuggingFace repo id。
        因此用 os.path.normpath 而非简单替换为正斜杠。
        """
        return os.path.normpath(self._raw_bge_m3_path) if self._raw_bge_m3_path else ""

    # ── Ollama 后端配置（bge_m3_provider=ollama 时生效） ──
    # Ollama 服务地址（兼容 OpenAI 风格 /api/embed 接口）
    ollama_base_url: str = env_str("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    # Ollama 中 BGE-M3 模型名（需 capabilities 含 embedding）
    ollama_bge_m3_model: str = env_str("OLLAMA_BGE_M3_MODEL", "bge-m3:latest")
    # 是否使用半精度（fp16）加速（仅 local 模式使用）
    bge_fp16: bool = env_bool("BGE_FP16", False)
    # 推理设备（仅 local 模式使用）：cpu / cuda
    bge_device: str = env_str("BGE_DEVICE", "cpu")
    # 向量维度（BGE-M3 默认 1024）
    embedding_dim: int = env_int("EMBEDDING_DIM", 1024)

    @property
    def use_ollama(self) -> bool:
        """是否使用 Ollama 作为向量化后端。"""
        return self.bge_m3_provider.strip().lower() == "ollama"


embedding_config = EmbeddingConfig()
