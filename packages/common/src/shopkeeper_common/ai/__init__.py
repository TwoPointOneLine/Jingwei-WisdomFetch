"""AI 能力封装：LLM 对话 / Embedding / Reranker 与统一出口。

业务代码统一通过 `shopkeeper_common.ai.llm_provider` 访问模型能力。
"""
from shopkeeper_common.ai.chat import LLMChat, chat, list_models, vl_chat
from shopkeeper_common.ai.embedding import (
    BGEM3Embedder,
    embed_documents,
    embed_query,
)
from shopkeeper_common.ai.providers import LLMProvider, llm_provider
from shopkeeper_common.ai.reranker import BGEReranker

__all__ = [
    "LLMChat",
    "chat",
    "vl_chat",
    "list_models",
    "BGEM3Embedder",
    "embed_documents",
    "embed_query",
    "BGEReranker",
    "LLMProvider",
    "llm_provider",
]
