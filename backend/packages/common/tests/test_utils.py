"""通用工具测试。"""
from pathlib import Path

import pytest
from jingwei_common.utils import (
    chunk_text,
    clean_text,
    ensure_dir,
    file_ext,
    is_pdf,
    md5,
    safe_get,
)
from jingwei_common.utils.prompt_utils import load_prompt


def test_md5():
    assert md5("hello") == "5d41402abc4b2a76b9719d911017c592"


def test_chunk_text():
    text = "a" * 1000
    chunks = chunk_text(text, size=100, overlap=10)
    assert len(chunks) >= 10
    assert all(len(c) <= 100 for c in chunks)
    assert chunk_text("") == []


def test_chunk_text_invalid():
    with pytest.raises(ValueError):
        chunk_text("x", size=10, overlap=20)


def test_clean_text():
    assert clean_text("  a   b  \n\t c ") == "a b c"


def test_safe_get():
    d = {"a": {"b": {"c": 1}}}
    assert safe_get(d, "a.b.c") == 1
    assert safe_get(d, "a.x") is None
    assert safe_get(d, "a.b.c.d", "default") == "default"


def test_file_utils(tmp_path: Path):
    assert file_ext("a.PDF") == ".pdf"
    assert is_pdf("a.pdf") is True
    assert is_pdf("a.txt") is False
    p = ensure_dir(tmp_path / "sub" / "dir")
    assert p.exists()
    assert p.is_dir()


def test_load_prompt():
    text = load_prompt("import_intent", topic="工商信息")
    assert "工商信息" in text
    assert "企业文档导入助手" in text
