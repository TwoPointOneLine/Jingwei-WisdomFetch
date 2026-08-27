"""
文档结构化元数据识别服务（FR-IMP-03）。

在切分/入库前，对文档做"主体级"结构化抽取，补充 PRD 要求的字段：
  - content_type   文档类型（产品说明书 / 资讯 / 公告 / 业务规则 / 风险揭示 / 知识库 等）
  - product_name   关联产品名称（如无则空串）
  - product_code   产品代码 / 产品编号（如无则空串）
  - risk_level     风险等级（R1~R5 / 低中高 / 未提及）
  - publish_date   发布日期（YYYY-MM-DD，无法识别则空串）

结果写入 state.doc_meta，随 chunks 一起落库 Milvus（动态字段自动存储）。
mock 模式给出保守默认值，避免阻塞主流程。
"""
import json
import re

from jingwei_common.ai.providers import llm_provider
from jingwei_common.config.lm_config import lm_config
from jingwei_common.logging import logger

_META_PROMPT = (
    "你是金融文档结构化抽取助手。请从给定文档中抽取主体级元数据，"
    "严格只输出如下 JSON（不要解释、不要多余文本）：\n"
    '{\n'
    '  "content_type": "产品说明书|资讯|公告|业务规则|风险揭示|知识库|其他",\n'
    '  "product_name": "关联产品名称，无则空串",\n'
    '  "product_code": "产品代码/编号，无则空串",\n'
    '  "risk_level": "R1|R2|R3|R4|R5|低|中|高|未提及",\n'
    '  "publish_date": "发布日期 YYYY-MM-DD，无法识别则空串"\n'
    "}\n\n"
    "【文档内容】\n{content}"
)

_DEFAULT_META = {
    "content_type": "知识库",
    "product_name": "",
    "product_code": "",
    "risk_level": "未提及",
    "publish_date": "",
}


def _merge_doc_meta(state) -> dict:
    """从 state 抽取必要信息，调用 LLM 识别结构化元数据，回写 state.doc_meta。"""
    doc_meta = dict(state.get("doc_meta") or {})
    raw_markdown = state.get("raw_markdown") or ""
    file_title = state.get("file_title", "")

    # mock 或内容过短 -> 直接用默认值（保留已有 source_file）
    if lm_config.mock or not raw_markdown.strip():
        doc_meta.update(_DEFAULT_META)
        return {"doc_meta": doc_meta}

    # 仅取前若干字符做识别，控制 token 成本
    snippet = raw_markdown[:4000]
    try:
        chat_model = llm_provider.chat()
        resp = chat_model.generate(_META_PROMPT.format(content=snippet + f"\n\n文件名提示：{file_title}"))
        text = getattr(resp, "output", None)
        if text is None and hasattr(resp, "choices"):
            text = resp.choices[0].message.content
        text = text or ""
        match = re.search(r"\{.*\}", text, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}
        for k in ("content_type", "product_name", "product_code", "risk_level", "publish_date"):
            v = (parsed.get(k) or "").strip()
            doc_meta[k] = v
        logger.info(f"元数据识别完成：{ {k: doc_meta.get(k) for k in _DEFAULT_META} }")
    except Exception as e:
        logger.warning(f"元数据 LLM 识别失败，使用默认值: {e}")
        doc_meta.update(_DEFAULT_META)

    return {"doc_meta": doc_meta}
