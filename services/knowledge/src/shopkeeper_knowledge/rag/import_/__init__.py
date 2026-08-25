"""
RAG 导入核心能力层：文档解析 -> 切块 -> 主体识别 -> 向量化 -> 入库。

本包是导入链（import_chain）底层核心能力的真实实现，提供与 state 无关的纯过程函数；
上层的 app/process/import_chain/services 仅做 re-export，保证单一逻辑来源。
"""
from shopkeeper_knowledge.rag.import_.embedding_service import generate_chunk_embeddings
from shopkeeper_knowledge.rag.import_.entry_service import resolve_input_file
from shopkeeper_knowledge.rag.import_.index_service import index_chunks
from shopkeeper_knowledge.rag.import_.item_name_service import recognize_and_index_item_name
from shopkeeper_knowledge.rag.import_.markdown_image_service import enrich_markdown_images
from shopkeeper_knowledge.rag.import_.pdf_parse_service import parse_pdf_to_markdown
from shopkeeper_knowledge.rag.import_.split_service import split_document

__all__ = [
    "resolve_input_file",
    "parse_pdf_to_markdown",
    "enrich_markdown_images",
    "split_document",
    "recognize_and_index_item_name",
    "generate_chunk_embeddings",
    "index_chunks",
]
