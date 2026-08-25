"""LLM 作答服务（兼容再导出）：核心实现见 app.rag.query.answer_service。

保留 _stream_text / _format_context 符号（api/query_server/main.py 直接引用）。
"""
from shopkeeper_query.rag.query.answer_service import _format_context, _stream_text, llm_answer

__all__ = ["llm_answer", "_stream_text", "_format_context"]
