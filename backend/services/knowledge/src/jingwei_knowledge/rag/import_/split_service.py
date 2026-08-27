"""
文档切块服务：标题层级粗切 + 超长段落细切，并补全切片元数据。

切块规则：
  - 按 Markdown 标题层级（# ~ ######）组织文档树，逐级粗切；
  - 单块超过 max_chars 时按段落/句子细切；
  - 代码块整体保护，不参与细切；
  - 相邻块重叠 overlap 个字符（5%~8%），保留跨块上下文；
  - 每个 chunk 补全 title / parent_title / file_title 元数据。
"""
import hashlib
import re

from jingwei_common.logging import logger

# 标题行匹配（# ~ ######）
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
# 代码块围栏
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MAX_CHARS = 1200
_OVERLAP = 80


def _split_long(text: str, max_chars: int = _MAX_CHARS, overlap: int = _OVERLAP) -> list[str]:
    """对超长文本按段落/句子细切，并加重叠窗口，代码块整体保护。"""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    # 保护代码块：先抽取为占位符
    fences: dict[str, str] = {}

    def _keep(m):
        key = f"\u0000FENCE{len(fences)}\u0000"
        fences[key] = m.group(0)
        return key

    protected = _FENCE_RE.sub(_keep, text)

    pieces = re.split(r"\n{2,}", protected)
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) + 2 <= max_chars:
            buf = f"{buf}\n\n{piece}" if buf else piece
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        # 单 piece 仍超长：按句子切
        if len(piece) > max_chars:
            for s in re.split(r"(?<=[。！？.!?])\s*", piece):
                if len(buf) + len(s) + 1 <= max_chars:
                    buf = f"{buf} {s}" if buf else s
                else:
                    if buf:
                        chunks.append(buf)
                    buf = s
        else:
            buf = piece
    if buf:
        chunks.append(buf)

    # 还原代码块占位 + 应用重叠窗口
    out: list[str] = []
    for i, c in enumerate(chunks):
        for k, v in fences.items():
            c = c.replace(k, v)
        c = c.strip()
        if i > 0 and overlap > 0 and len(out[-1]) >= overlap:
            c = out[-1][-overlap:] + "\n" + c
        out.append(c)
    return out


def _extract_segments(raw_markdown: str, file_title: str) -> list[tuple[str, str, str]]:
    """返回 [(content, title, parent_title), ...]，先粗切（按标题）再细切。"""
    headings = list(_HEADING_RE.finditer(raw_markdown))
    segs: list[tuple[str, str, str]] = []

    if not headings:
        for seg in _split_long(raw_markdown):
            segs.append((seg, "", ""))
        return segs

    for idx, h in enumerate(headings):
        start = h.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(raw_markdown)
        section = raw_markdown[start:end].strip()
        if not section:
            continue
        title = h.group(2).strip()
        level = len(h.group(1))
        parent = ""
        # 向上找最近的上一级标题作为 parent
        for ph in reversed(headings[:idx]):
            if len(ph.group(1)) < level:
                parent = ph.group(2).strip()
                break
        for seg in _split_long(section):
            segs.append((seg, title, parent))
    return segs


def split_document(state) -> dict:
    """
    把 state.raw_markdown 切分为带元数据的 chunk 列表，回写 chunks。
    每个 chunk 附带文档级结构化元数据 doc_meta（FR-IMP-03），用于后续落库与引用溯源。
    """
    raw_markdown = state.get("raw_markdown", "")
    file_title = state.get("file_title", "untitled")
    doc_meta = state.get("doc_meta") or {}

    segs = _extract_segments(raw_markdown, file_title)
    chunks = []
    for content, title, parent_title in segs:
        cid = hashlib.md5(f"{file_title}|{title}|{content}".encode()).hexdigest()[:16]
        chunks.append(
            {
                "chunk_id": cid,
                "content": content,
                "title": title,
                "parent_title": parent_title,
                "file_title": file_title,
                "doc_meta": doc_meta,
            }
        )

    logger.info(f"切块完成，共 {len(chunks)} 个 chunk")
    return {"chunks": chunks}
