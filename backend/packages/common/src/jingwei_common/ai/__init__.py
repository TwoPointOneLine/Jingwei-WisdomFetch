"""AI 能力封装：LLM 对话 / Embedding / Reranker 与统一出口。

业务代码统一通过 `jingwei_common.ai.llm_provider` 访问模型能力。
"""
# 必须在任何 FlagEmbedding import 之前安装 transformers>=5 兼容性 shim，
# 否则 FlagEmbedding 的 reranker 子模块在 transformers 5.x 下会因缺失
# is_torch_fx_available 而无法导入。
from jingwei_common.ai._flagembedding_compat import ensure_flagembedding_importable

ensure_flagembedding_importable()

from jingwei_common.ai.chat import LLMChat, chat, list_models, vl_chat  # noqa: E402
from jingwei_common.ai.embedding import (  # noqa: E402
    BGEM3Embedder,
    embed_documents,
    embed_query,
)
from jingwei_common.ai.providers import LLMProvider, llm_provider  # noqa: E402
from jingwei_common.ai.reranker import BGEReranker  # noqa: E402

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
