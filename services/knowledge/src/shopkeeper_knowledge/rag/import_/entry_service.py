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
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger

from shopkeeper_knowledge.infra.object_storage.minio_store import object_storage


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
    is_md = file_ext in (".md", ".markdown")
    is_pdf = file_ext == ".pdf"

    return {
        "local_file_path": local_file_path,
        "file_title": file_title,
        "file_ext": file_ext,
        "is_md_read_enabled": is_md,
        "is_pdf_read_enabled": is_pdf,
    }
