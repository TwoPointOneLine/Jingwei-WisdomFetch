"""导入文件格式白名单（单一事实来源）。

需求 §4 定义了可导入的内容范围，但**并非所有格式都有对应解析器**。
为避免"上传成功但零条入库"的静默失败（G-01），在此集中声明：

  - SUPPORTED_EXTS：当前真正支持解析的扩展名集合
  - is_supported()：上传/入口处的准入校验
  - unsupported_message()：面向用户的中文提示
  - accept_attr()：供前端 <input accept> 复用，保证前后端一致

新增格式支持时（如阶段三的 TXT/HTML/DOCX），只需扩展 SUPPORTED_EXTS
并在 import_chain/main_graph.py 中补对应路由分支，前端 accept 自动跟随。
"""
from __future__ import annotations

import os

# 当前具备解析器的扩展名（小写，含点号）
# G-09：新增 TXT / HTML / HTM / DOCX 解析（零三方依赖）。
SUPPORTED_EXTS: frozenset[str] = frozenset(
    {
        ".pdf",  # marker / PyMuPDF -> Markdown
        ".md",  # 直读
        ".markdown",  # 直读
        ".txt",  # 直读（去尾部空白）
        ".html",  # 解析为 Markdown
        ".htm",  # 解析为 Markdown
        ".docx",  # 解包 document.xml -> Markdown（zipfile + ElementTree，零依赖）
    }
)

# 面向用户的格式展示名（按展示顺序）
_DISPLAY_NAMES = {
    ".pdf": "PDF",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".txt": "TXT",
    ".html": "HTML",
    ".htm": "HTML",
    ".docx": "Word",
}


def normalize_ext(filename: str) -> str:
    """取文件名的小写扩展名（含点号）；无扩展名返回空串。"""
    return os.path.splitext(filename or "")[1].lower()


def is_supported(filename: str) -> bool:
    """判断文件名是否属于受支持的导入格式。"""
    return normalize_ext(filename) in SUPPORTED_EXTS


def supported_display() -> str:
    """返回去重后的格式展示名，如 'PDF、Markdown'。"""
    names: list[str] = []
    for ext in sorted(SUPPORTED_EXTS):
        name = _DISPLAY_NAMES.get(ext, ext.lstrip(".").upper())
        if name not in names:
            names.append(name)
    return "、".join(names)


def unsupported_message(filename: str) -> str:
    """构造面向用户的明确报错文案（含支持清单）。"""
    ext = normalize_ext(filename)
    if not ext:
        return f"文件「{filename}」缺少扩展名，无法识别格式。当前支持：{supported_display()}。"
    return (
        f"不支持的文件格式「{ext}」（文件：{filename}）。"
        f"当前支持：{supported_display()}。请转换格式后重新上传。"
    )


def accept_attr() -> str:
    """供前端 <input type="file" accept> 使用，如 '.pdf,.md,.markdown'。"""
    return ",".join(sorted(SUPPORTED_EXTS))


class UnsupportedFileFormatError(ValueError):
    """导入图入口处抛出的格式不支持异常（携带可直接展示的文案）。"""

    def __init__(self, filename: str):
        super().__init__(unsupported_message(filename))
        self.filename = filename


__all__ = [
    "SUPPORTED_EXTS",
    "UnsupportedFileFormatError",
    "accept_attr",
    "is_supported",
    "normalize_ext",
    "supported_display",
    "unsupported_message",
]
