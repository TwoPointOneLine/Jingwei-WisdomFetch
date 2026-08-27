"""
大模型对话封装。

基于 LangChain ChatOpenAI，兼容 OpenAI 协议。根据配置支持：
- DashScope（在线）：走 https://dashscope.aliyuncs.com/compatible-mode/v1
- 本地模型（Ollama / LM Studio / vLLM）：走本地 base_url
"""
from langchain_openai import ChatOpenAI

from jingwei_common.config.lm_config import lm_config


class LLMChat:
    """对话模型封装，兼容 DashScope 与本地 OpenAI 兼容服务。"""

    _chat: ChatOpenAI | None = None

    @classmethod
    def get_chat(cls, model: str | None = None) -> ChatOpenAI:
        if cls._chat is None or model is not None:
            cls._chat = ChatOpenAI(
                model=model or lm_config.active_default_model,
                api_key=lm_config.active_api_key,
                base_url=lm_config.active_base_url,
                temperature=0.3,
                max_retries=2,
            )
        return cls._chat

    @classmethod
    def get_vl_chat(cls) -> ChatOpenAI:
        """多模态（视觉理解）模型。"""
        return cls.get_chat(lm_config.active_vl_model)


def chat(model: str | None = None) -> ChatOpenAI:
    return LLMChat.get_chat(model)


def vl_chat() -> ChatOpenAI:
    return LLMChat.get_vl_chat()


def list_models() -> list[dict]:
    """返回可用对话模型列表。

    本地 provider 时动态拉取本地服务（Ollama 等）的模型列表；
    DashScope 时返回内置的常用模型。
    """
    if lm_config.is_local:
        try:
            import requests

            resp = requests.get(f"{lm_config.active_base_url}/models", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            models = []
            for m in items:
                mid = m.get("id") or m.get("model") or ""
                if mid:
                    models.append({"id": mid, "name": mid, "description": "本地模型"})
            if models:
                return models
        except Exception:
            pass
        # 拉取失败时回退到配置的默认本地模型
        return [
            {
                "id": lm_config.active_default_model,
                "name": lm_config.active_default_model,
                "description": "本地模型（默认）",
            }
        ]

    # DashScope：内置常用模型
    default = lm_config.active_default_model
    models = [
        {"id": default, "name": f"{default}（默认）", "description": "通用对话模型"},
        {"id": lm_config.active_vl_model, "name": lm_config.active_vl_model, "description": "多模态视觉模型"},
        {"id": "qwen-plus", "name": "qwen-plus", "description": "通用对话模型"},
        {"id": "qwen-turbo", "name": "qwen-turbo", "description": "轻量快速模型"},
        {"id": "qwen-max", "name": "qwen-max", "description": "高性能旗舰模型"},
    ]
    seen, unique = set(), []
    for m in models:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    return unique
