"""
Markdown 图片服务：抽取并转写 Markdown 内本地图片链接，保证切片内容自包含。

对本地相对路径图片做校验；对 http(s) 外链原样保留。返回图片清单。
"""
import os
import re

from jingwei_common.logging import logger

_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def enrich_markdown_images(state) -> dict:
    """
    处理 state.raw_markdown 中的图片链接，回写：
      - raw_markdown: 可能已规整的图片路径
      - image_list: [{alt, src, is_local}]
    """
    raw_markdown = state.get("raw_markdown", "")
    base_dir = os.path.dirname(state.get("local_file_path", "") or "")

    image_list = []
    for alt, src in _IMG_RE.findall(raw_markdown):
        is_local = not src.startswith(("http://", "https://", "data:"))
        if is_local and base_dir:
            abs_path = os.path.normpath(os.path.join(base_dir, src))
            if os.path.exists(abs_path):
                # 将相对路径替换为绝对路径，保证切片后图片可寻址
                raw_markdown = raw_markdown.replace(f"]({src})", f"]({abs_path})", 1)
                src = abs_path
        image_list.append({"alt": alt, "src": src, "is_local": is_local})

    logger.info(f"Markdown 图片处理完成，共 {len(image_list)} 张")
    return {"raw_markdown": raw_markdown, "image_list": image_list}
