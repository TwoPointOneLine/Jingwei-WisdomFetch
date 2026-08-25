"""
PDF 解析服务：把 PDF 转为 Markdown（保留标题层级与版面结构）。

优先使用 marker（版面感知），缺失时降级为 PyMuPDF 纯文本提取。
"""
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger


def parse_pdf_to_markdown(state) -> dict:
    """
    解析 state.local_file_path（PDF）为 Markdown，回写：
      - raw_markdown: 解析后的 Markdown 文本
      - is_markdown_ready: True
    mock 模式直接返回占位 Markdown，避免依赖解析器。
    """
    pdf_path = state.get("local_file_path", "")

    if lm_config.mock or not pdf_path:
        logger.info("PDF 解析（mock/占位）：返回简单占位 Markdown")
        raw_markdown = f"# {state.get('file_title', 'document')}\n\n（PDF 占位内容）\n"
        return {"raw_markdown": raw_markdown, "is_markdown_ready": True}

    try:
        from marker.config.parser import ConfigParser  # type: ignore
        from marker.converters.pdf import PdfConverter  # type: ignore
        from marker.models import create_model_dict  # type: ignore
        from marker.output import text_from_rendered  # type: ignore

        config = ConfigParser({"output_format": "markdown"}).generate_config_dict()
        converter = PdfConverter(
            config=config,
            model_dict=create_model_dict(),
            artifact_dict=None,
            processor_list=None,
        )
        rendered = converter(pdf_path)
        raw_markdown = text_from_rendered(rendered)
        logger.info(f"marker 解析完成，长度 {len(raw_markdown)}")
    except Exception as e:
        logger.warning(f"marker 不可用，降级 PyMuPDF: {e}")
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            parts = [page.get_text("text") for page in doc]
            raw_markdown = "\n\n".join(p for p in parts if p.strip())
            doc.close()
        except Exception as e2:
            logger.warning(f"PyMuPDF 也不可用，返回占位: {e2}")
            raw_markdown = f"# {state.get('file_title', 'document')}\n\n（PDF 解析失败占位）\n"

    return {"raw_markdown": raw_markdown, "is_markdown_ready": True}
