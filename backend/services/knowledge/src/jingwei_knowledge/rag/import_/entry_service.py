"""
入口服务：把任意输入解析为统一的待处理文件路径。

支持：
  - 本地文件路径（local_file_path）
  - HTTP/HTTPS 临时链接（url）
  - 已上传文件（file_id 指向 minio）
下载到本地临时目录并返回绝对路径，同时回写 file_title / 文件类型标识。
"""
import os
import tempfile

import httpx
from jingwei_common.config.lm_config import lm_config
from jingwei_common.logging import logger

from jingwei_knowledge.infra.object_storage.minio_store import object_storage
from jingwei_knowledge.rag.import_.doc_format import (
    SUPPORTED_EXTS,
    UnsupportedFileFormatError,
)


def resolve_input_file(state) -> dict:
    """
    解析输入来源，统一为本地文件路径。就地更新 state 返回增量字段：
      - local_file_path: 本地绝对路径
      - file_title: 文件名（无后缀）
      - file_ext: 小写后缀（.pdf / .md / ...）
      - is_md_read_enabled / is_pdf_read_enabled: 路由标志
    """
    file_id = state.get("file_id", "")
    local_file_path = state.get("local_file_path", "")
    url = state.get("url", "")

    # 1) 本地路径直接复用
    if local_file_path:
        pass
    # 2) file_id -> minio 下载
    elif file_id:
        try:
            data = object_storage.download_bytes(file_id)
            tmp = os.path.join(tempfile.gettempdir(), file_id)
            with open(tmp, "wb") as f:
                f.write(data)
            local_file_path = tmp
            logger.info(f"从 minio 下载 file_id={file_id} -> {local_file_path}")
        except Exception as e:
            logger.warning(f"minio 下载失败，回退为空路径: {e}")
            local_file_path = ""
    # 3) url -> http 下载
    elif url:
        try:
            resp = httpx.get(url, timeout=30)
            resp.raise_for_status()
            suffix = os.path.splitext(url.split("?")[0])[1] or ".tmp"
            tmp = os.path.join(tempfile.gettempdir(), f"dl_{abs(hash(url))}{suffix}")
            with open(tmp, "wb") as f:
                f.write(resp.content)
            local_file_path = tmp
            logger.info(f"从 url 下载 {url} -> {local_file_path}")
        except Exception as e:
            logger.warning(f"url 下载失败，回退为空路径: {e}")
            local_file_path = ""

    if not local_file_path:
        if not lm_config.mock:
            raise ValueError("缺少可用输入：file_id / local_file_path / url 至少一项")

    file_ext = os.path.splitext(local_file_path)[1].lower() if local_file_path else ""
    file_title = (
        os.path.splitext(os.path.basename(local_file_path))[0] if local_file_path else "untitled"
    )
    source_file = os.path.basename(local_file_path) if local_file_path else ""

    # G-01：入口处硬校验格式，避免不支持的文件静默走 END 导致"成功但零条入库"。
    if file_ext and file_ext not in SUPPORTED_EXTS:
        raise UnsupportedFileFormatError(source_file or local_file_path)

    is_md = file_ext in (".md", ".markdown")
    is_pdf = file_ext == ".pdf"
    # G-09：新增 txt/html/htm/docx 的解析路由标志
    is_text = file_ext == ".txt"
    is_html = file_ext in (".html", ".htm")
    is_docx = file_ext == ".docx"

    # FR-IMP-03 / G-04：文档级元数据初始含来源文件名与绝对路径，
    # 其余字段（content_type/product_name/.../institution_name/industry/market/entry_name）
    # 由 metadata 识别阶段补全；entry_name 先留空，由切块阶段填入首标题。
    doc_meta = {
        "source_file": source_file,
        "source_path": local_file_path,
        "entry_name": "",
    }

    # G-09：除 PDF 外的所有受支持格式，统一在入口直接解析为 raw_markdown，
    # 避免各自的 LangGraph 路由分支。PDF 仍走 node_pdf_to_md（重型解析/图片）。
    raw_markdown = ""
    is_markdown_ready = False
    if is_md and local_file_path:
        try:
            with open(local_file_path, encoding="utf-8", errors="ignore") as f:
                raw_markdown = f.read()
            is_markdown_ready = True
            logger.info(f"Markdown 文件读取完成，长度 {len(raw_markdown)}")
        except Exception as e:
            logger.warning(f"Markdown 文件读取失败: {e}")
    elif (is_text or is_html or is_docx) and local_file_path:
        try:
            from jingwei_knowledge.rag.import_.parse_service import parse_to_markdown

            raw_markdown = parse_to_markdown(local_file_path)
            is_markdown_ready = True
            logger.info(f"{file_ext} 解析完成，Markdown 长度 {len(raw_markdown)}")
        except Exception as e:
            logger.warning(f"{file_ext} 解析失败: {e}")

    return {
        "local_file_path": local_file_path,
        "file_title": file_title,
        "file_ext": file_ext,
        "is_md_read_enabled": is_md or is_text or is_html or is_docx,
        "is_pdf_read_enabled": is_pdf,
        "raw_markdown": raw_markdown,
        "is_markdown_ready": is_markdown_ready,
        "doc_meta": doc_meta,
    }
