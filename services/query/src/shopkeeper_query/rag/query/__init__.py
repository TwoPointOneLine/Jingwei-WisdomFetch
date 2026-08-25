"""
RAG 查询核心能力层：主体确认 -> 检索（向量/HyDE/联网）-> RRF 融合 -> 重排 -> 答案生成。

本包是查询链（query_chain）底层核心能力的真实实现，提供与 state 无关的纯过程函数；
上层的 app/process/query_chain/services 仅做 re-export，保证单一逻辑来源。
"""
from shopkeeper_query.rag.query.answer_service import _format_context, _stream_text, llm_answer
from shopkeeper_query.rag.query.embedding_search_service import vector_retrieve
from shopkeeper_query.rag.query.hyde_search_service import hyde_retrieve
from shopkeeper_query.rag.query.item_name_confirm_service import confirm_item_name
from shopkeeper_query.rag.query.rerank_service import rerank_documents
from shopkeeper_query.rag.query.rrf_service import fuse_by_rrf
from shopkeeper_query.rag.query.web_search_service import web_search

__all__ = [
    "confirm_item_name",
    "vector_retrieve",
    "hyde_retrieve",
    "web_search",
    "fuse_by_rrf",
    "rerank_documents",
    "llm_answer",
    "_stream_text",
    "_format_context",
]
