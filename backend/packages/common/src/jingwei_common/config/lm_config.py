"""
大模型（LLM）配置。

支持两种 provider：
- dashscope：通义千问 DashScope 兼容 OpenAI 协议（在线）
- local：本地 OpenAI 兼容服务（如 Ollama / LM Studio / vLLM）
"""
from jingwei_common.config.common import env_bool, env_str


class LMConfig:
    # provider: dashscope | local
    provider: str = env_str("LLM_PROVIDER", "dashscope")

    # ---- DashScope（在线）----
    # DashScope / 百炼 API Key，同时作为 OpenAI 协议兼容的 api_key
    api_key: str = env_str("OPENAI_API_KEY", "")
    # 兼容 OpenAI 协议的 Base URL
    base_url: str = env_str(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    # 默认文本对话模型
    default_model: str = env_str("LLM_DEFAULT_MODEL", "qwen-plus")
    # 多模态（视觉理解）模型
    vl_model: str = env_str("VL_MODEL", "qwen-vl-max")

    # ---- 本地模型（Ollama / LM Studio / vLLM）----
    local_base_url: str = env_str(
        "LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"
    )
    # 本地默认对话模型（需在本地服务中存在）
    local_default_model: str = env_str("LOCAL_LLM_MODEL", "qwen3:8b")
    # 本地多模态/备用模型
    local_vl_model: str = env_str("LOCAL_VL_MODEL", "qwen2.5-coder:14b")

    # 模拟模式：为人工测试前端链路提供模拟回答（不调用真实 LLM）
    mock: bool = env_bool("LLM_MOCK", False)

    # 联网检索开关：默认关闭，保证回答仅基于已导入的内部资料（FR-QA-06）。
    # 仅在运维显式开启 WEB_SEARCH_ENABLED=true 时，才将外网结果混入重排与生成。
    web_search_enabled: bool = env_bool("WEB_SEARCH_ENABLED", False)

    @property
    def is_local(self) -> bool:
        return self.provider == "local"

    @property
    def active_base_url(self) -> str:
        """当前生效的 base_url。"""
        return self.local_base_url if self.is_local else self.base_url

    @property
    def active_api_key(self) -> str:
        """当前生效的 api_key（本地模型用占位即可）。"""
        return "ollama" if self.is_local else self.api_key

    @property
    def active_default_model(self) -> str:
        return self.local_default_model if self.is_local else self.default_model

    @property
    def active_vl_model(self) -> str:
        return self.local_vl_model if self.is_local else self.vl_model


lm_config = LMConfig()
