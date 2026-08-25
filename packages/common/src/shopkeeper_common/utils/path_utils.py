"""
路径与文件工具。
"""
import os
import tempfile
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，返回 Path。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def file_ext(filename: str) -> str:
    """返回小写扩展名（含点），如 '.pdf'。"""
    return Path(filename).suffix.lower()


def is_pdf(filename: str) -> bool:
    return file_ext(filename) == ".pdf"


def unique_filename(base: str, ext: str = "") -> str:
    """基于时间戳生成唯一文件名。"""
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{base}_{ts}{ext}"


def temp_path(ext: str = "") -> Path:
    """返回系统临时目录下的一个临时文件路径。"""
    fd, name = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    return Path(name)


__all__ = ["ensure_dir", "file_ext", "is_pdf", "unique_filename", "temp_path"]
