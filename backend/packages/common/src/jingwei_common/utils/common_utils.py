"""
通用工具。
"""
import hashlib
import re
from typing import Any


def md5(text: str) -> str:
    """计算字符串 md5。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def chunk_text(text: str, size: int = 1000, overlap: int = 100):
    """按字符滑动窗口切分文本，返回片段列表。"""
    if size <= overlap:
        raise ValueError("size 必须大于 overlap")
    if not text:
        return []
    chunks = []
    start = 0
    step = size - overlap
    while start < len(text):
        chunk = text[start : start + size]
        if chunk.strip():
            chunks.append(chunk)
        start += step
    return chunks


def clean_text(text: str) -> str:
    """去除多余空白与不可见字符。"""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_get(d: dict, path: str, default: Any = None):
    """按 a.b.c 路径安全取值。"""
    cur: Any = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


__all__ = ["md5", "chunk_text", "clean_text", "safe_get"]
