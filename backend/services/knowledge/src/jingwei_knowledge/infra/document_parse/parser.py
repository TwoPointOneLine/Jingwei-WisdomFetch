"""
MinerU 文档解析封装（infra 层）。

调用 MinerU 解析服务将 PDF 转为 Markdown，供后续切片节点使用。
服务未配置时降级为读取本地文件。
"""
import requests
from jingwei_common.config.mineru_config import mineru_config
from jingwei_common.logging import logger, step_log


class MinerUParser:
    """MinerU PDF 解析封装。"""

    @step_log("mineru_parse")
    def parse_pdf(self, pdf_path: str, output_dir: str | None = None) -> dict:
        """
        解析 PDF。
        :param pdf_path: 本地 PDF 路径或 MinIO 对象名
        :return: {"markdown": str, "images": [...], "raw": ...}
        """
        if not mineru_config.api_url:
            raise RuntimeError("MINERU_API_URL 未配置，无法调用解析服务")
        logger.info(f"调用 MinerU 解析: {pdf_path}")
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                mineru_config.api_url,
                files={"file": f},
                data={"output_dir": output_dir or ""},
                timeout=600,
            )
        resp.raise_for_status()
        return resp.json()


# 全局实例
document_parser = MinerUParser()
