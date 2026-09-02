"""通用文档解析服务（G-09）：将多种格式统一转换为 Markdown。

支持的格式：
  - .md / .markdown：直读
  - .txt：直读（去尾部多余空白）
  - .pdf：marker / PyMuPDF（复用 pdf_parse_service）
  - .html / .htm：标准库 html.parser 抽取正文转为 Markdown
  - .docx：zipfile + xml.etree 解包 document.xml，转 Markdown（零三方依赖）

新增格式只需在 _dispatch 中增加分支，前端白名单（doc_format.SUPPORTED_EXTS）
会自动跟随 accept 提示。
"""
from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from jingwei_knowledge.rag.import_.doc_format import normalize_ext

_TXT_EXTS = {".txt"}
_MD_EXTS = {".md", ".markdown"}
_HTML_EXTS = {".html", ".htm"}
_DOCX_EXTS = {".docx"}


class _HtmlToMarkdown(HTMLParser):
    """极简 HTML -> Markdown 转换器（仅保留可读正文与基础结构）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip = 0  # <script>/<style> 嵌套深度
        self._list_stack: list[str] = []
        self._in_pre = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._out.append("\n" + "#" * level + " ")
        elif tag == "p":
            self._out.append("\n\n")
        elif tag == "br":
            self._out.append("\n")
        elif tag in ("ul", "ol"):
            self._list_stack.append(tag)
            self._out.append("\n")
        elif tag == "li":
            self._out.append("\n- ")
        elif tag == "blockquote":
            self._out.append("\n> ")
        elif tag == "hr":
            self._out.append("\n\n---\n\n")
        elif tag == "pre":
            self._in_pre = True
            self._out.append("\n```\n")
        elif tag == "code":
            if not self._in_pre:
                self._out.append("`")
        elif tag == "a":
            self._out.append("[")
        elif tag in ("strong", "b"):
            self._out.append("**")
        elif tag in ("em", "i"):
            self._out.append("*")
        elif tag == "table":
            self._out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self._out.append("\n")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
        elif tag == "pre":
            self._in_pre = False
            self._out.append("\n```\n")
        elif tag == "code":
            if not self._in_pre:
                self._out.append("`")
        elif tag == "a":
            href = ""
            self._out.append(f"]({href})")
        elif tag in ("strong", "b"):
            self._out.append("**")
        elif tag in ("em", "i"):
            self._out.append("*")

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_pre:
            self._out.append(data)
        else:
            # 折叠多余空白，保留基本可读性
            text = data.replace("\u00a0", " ")
            self._out.append(text)

    def get_markdown(self) -> str:
        raw = "".join(self._out)
        # 清理空行与多余空格
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        return raw.strip()


def _html_to_markdown(content: str) -> str:
    parser = _HtmlToMarkdown()
    parser.feed(content)
    return parser.get_markdown()


def _docx_to_markdown(path: str) -> str:
    """从 .docx 解包 word/document.xml，提取段落/标题/列表/表格转为 Markdown。"""
    with zipfile.ZipFile(path) as zf:
        xml_path = "word/document.xml"
        if xml_path not in zf.namelist():
            raise ValueError("非法的 docx 文件：缺少 word/document.xml")
        xml_data = zf.read(xml_path)

    import xml.etree.ElementTree as ET

    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }
    root = ET.fromstring(xml_data)
    body = root.find("w:body", ns)
    if body is None:
        return ""

    lines: list[str] = []

    def _text_of(p):
        parts = []
        for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
            parts.append(t.text or "")
        return "".join(parts)

    # 递归处理正文块（段落 + 表格）
    def _walk(elem):
        for child in list(elem):
            tag = child.tag.split("}")[-1]
            if tag == "p":
                style = _style_at_p(child)
                text = _text_of(child)
                is_heading = bool(style) and (style.startswith("Heading") or style == "Title")
                if is_heading:
                    # 估算标题级别
                    m = re.search(r"(\d)", style or "")
                    level = int(m.group(1)) if m else 1
                    lines.append("#" * max(1, min(level, 6)) + " " + text)
                else:
                    if text.strip():
                        lines.append(text)
                _walk(child)
            elif tag == "tbl":
                rows = []
                for row in child.findall("w:tr", ns):
                    cells = []
                    for cell in row.findall("w:tc", ns):
                        cell_text = _text_of(cell).replace("\n", " ").strip()
                        cells.append(cell_text)
                    rows.append(cells)
                if rows:
                    header = rows[0]
                    lines.append("| " + " | ".join(header) + " |")
                    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                    for r in rows[1:]:
                        lines.append("| " + " | ".join(r) + " |")
                    lines.append("")
                _walk(child)
            else:
                _walk(child)

    def _style_at_p(p):
        ppr = p.find("w:pPr", ns)
        if ppr is None:
            return None
        pstyle = ppr.find("w:pStyle", ns)
        if pstyle is None:
            return None
        return pstyle.get(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
        )

    _walk(body)
    return "\n\n".join(line for line in lines if line is not None).strip()


def parse_to_markdown(path: str) -> str:
    """按扩展名统一解析为 Markdown。不支持的扩展名抛 ValueError。"""
    ext = normalize_ext(path)
    if ext in _MD_EXTS:
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    if ext in _TXT_EXTS:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return re.sub(r"[ \t]+\n", "\n", text).strip()
    if ext in _HTML_EXTS:
        raw = Path(path).read_text(encoding="utf-8", errors="ignore")
        return _html_to_markdown(raw)
    if ext in _DOCX_EXTS:
        return _docx_to_markdown(path)
    if ext == ".pdf":
        from jingwei_knowledge.rag.import_.pdf_parse_service import parse_pdf_to_markdown

        md, _ = parse_pdf_to_markdown(path)
        return (md or "").strip()
    raise ValueError(f"暂不支持解析的格式：{ext or '未知'}")


__all__ = ["parse_to_markdown"]
