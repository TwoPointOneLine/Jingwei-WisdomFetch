"""
LLM 作答服务（RAG 生成）：基于重排后的上下文生成答案，支持流式增量推送（SSE）。

依赖：
  - 重排后的 rerank_documents 作为上下文；
  - 通过 delta_queue / SSE 把生成内容逐字推送给前端。
无检索上下文时优雅降级为友好提示。
"""
import time

from jingwei_common.ai.providers import llm_provider
from jingwei_common.compliance import (
    AI_DISCLAIMER,
    EXTERNAL_SOURCE_NOTE,
    NO_CONTEXT_REPLY,
    apply_compliance,
)
from jingwei_common.config.lm_config import lm_config
from jingwei_common.logging import logger
from jingwei_common.web.sse_utils import push_to_session

# 记录每个 session 是否已做过 mock 流式，避免 fan-in 多次触发 rag 时重复 sleep
_MOCK_STREAMED: set[str] = set()


def _stream_text(session_id: str, text: str, need_stream: bool, mock: bool = False):
    """把完整文本逐字（每 3 字符）推送为 delta，供前端呈现流式效果。

    mock/降级文案需要加小延迟，模拟真实 LLM 的流式节奏；但 mock 场景下
    rag 可能被 fan-in 多次触发，第二次起不再 sleep（已推送过），避免重复耗时。
    """
    if need_stream:
        if mock and session_id in _MOCK_STREAMED:
            # 已流式过（fan-in 重复触发），直接一次性推送，不再 sleep
            push_to_session(session_id, "delta", {"text": text})
            return
        for i in range(0, len(text), 3):
            push_to_session(session_id, "delta", {"text": text[i : i + 3]})
            time.sleep(0.012)
        if mock:
            _MOCK_STREAMED.add(session_id)


def _format_context(reranked: list) -> str:
    parts = []
    for i, d in enumerate(reranked, 1):
        content = d.get("content") or d.get("snippet") or ""
        source = d.get("source", "doc")
        parts.append(f"[资料{i}]({source})\n{content}")
    return "\n\n".join(parts)


# FR-QA-02：问题类型分类（用于回答风格引导，不改变检索路径）
_QUERY_TYPES = ["产品咨询", "知识问答", "资讯动态", "公告通知", "风险揭示", "业务办理", "通用"]


def _classify_query_type(query: str) -> str:
    """识别问题所属类型（六类 + 通用），用于提示词引导组织方式。

    mock 模式或识别失败统一返回「通用」，不影响检索与主流程。
    """
    if lm_config.mock:
        return "通用"
    try:
        chat_model = llm_provider.chat()
        prompt = (
            "你是金融问答分类器。请将用户问题归类到以下之一，仅输出类别名称本身"
            f"（不要解释）：{_QUERY_TYPES}\n\n用户问题：{query}"
        )
        resp = chat_model.generate(prompt)
        text = getattr(resp, "output", None)
        if text is None and hasattr(resp, "choices"):
            text = resp.choices[0].message.content
        label = (text or "").strip()
        if label in _QUERY_TYPES:
            return label
    except Exception as e:
        logger.warning(f"问题分类失败，回退通用: {e}")
    return "通用"


_TYPE_GUIDANCE = {
    "产品咨询": "请重点组织产品要素（名称/代码/类型/风险/费用/规则），缺失项注明「资料未提及」。",
    "资讯动态": "请突出时效性与信息来源时间，并提示以官方渠道最新发布为准。",
    "公告通知": "请突出生效时间与适用对象，并提示以官方公告原文为准。",
    "风险揭示": "请充分提示相关风险，并附风险提示语。",
    "业务办理": "请说明办理路径/前提条件，并提示以官方业务规则为准。",
    "知识问答": "请基于检索资料给出清晰解释，必要时分点。",
    "通用": "请基于检索资料准确作答。",
}


def _build_citations(reranked: list) -> list:
    """由重排结果构造结构化来源引用（FR-CITE-01/02），供前端可展开可信标记。

    每条含：标题、来源类型(milvus/web)、内容类型、产品名/代码、风险等级、
    发布日期、来源文件名；web 来源额外标注 external=True（看官方渠道提示）。
    """
    citations = []
    for i, d in enumerate(reranked, 1):
        meta = d.get("doc_meta") or {}
        citations.append(
            {
                "index": i,
                "title": d.get("title") or meta.get("product_name") or d.get("item_name") or "",
                "source": d.get("source", "milvus"),
                "external": bool(d.get("external")),
                "content_type": meta.get("content_type") or d.get("content_type") or "",
                "product_name": meta.get("product_name") or d.get("product_name") or "",
                "product_code": meta.get("product_code") or d.get("product_code") or "",
                "risk_level": meta.get("risk_level") or d.get("risk_level") or "",
                "publish_date": meta.get("publish_date") or d.get("publish_date") or "",
                "source_file": meta.get("source_file") or d.get("source_file") or "",
            }
        )
    return citations


def llm_answer(state) -> dict:
    """
    取出重排后的上下文，构造 Prompt，调用 LLM 流式生成，增量推入 SSE，
    最终写入 llm_output。
    """
    reranked = state.get("rerank_documents") or []
    user_query = state.get("user_query") or state["query"]
    session_id = state.get("session_id", "")
    need_stream = bool(state.get("need_stream_output"))

    # 模拟模式：为人工测试前端链路提供模拟回答（不调用真实 LLM）
    if lm_config.mock:
        logger.info("LLM_MOCK 已开启，返回模拟回答")
        mock_text = (
            f"这是模拟回答（LLM_MOCK 模式）。您的问题是：{user_query}。"
            "当前为人工测试模式，前端完整链路（SSE 流式 / 持久化 / 会话）已可正常验证。"
            "关闭 LLM_MOCK 后即调用真实本地模型。"
        )
        mock_text = f"{mock_text}\n\n{AI_DISCLAIMER}"
        _stream_text(session_id, mock_text, need_stream, mock=True)
        return {"llm_output": mock_text, "citations": []}

    # 无检索上下文时使用 PRD 标准拒答话术（FR-QA-05），不编造、不转通用助手。
    if not reranked:
        logger.info("无检索上下文，返回标准拒答话术")
        output = NO_CONTEXT_REPLY
        _stream_text(session_id, output, need_stream, mock=False)
        return {"llm_output": output, "citations": []}
    else:
        # 识别是否混入了外网来源（仅 WEB_SEARCH_ENABLED=true 时才可能出现）
        has_external = any(d.get("external") for d in reranked)
        context = _format_context(reranked)
        # FR-QA-06：默认可信边界为已导入的内部资料；引入外网来源时仅作参考并显式提示看官方渠道。
        external_directive = ""
        if has_external:
            external_directive = (
                "其中标记为 (web) 的资料来自公开网络，仅供参考，不构成投资建议；"
                "涉及具体产品要素、收益与风险，应以官方披露文件与持牌机构口径为准。\n"
            )
        # FR-QA-03：当资料命中产品/结构化内容时，按四段式组织，缺失字段填"资料未提及"。
        product_meta = next(
            (d.get("doc_meta") or {} for d in reranked if (d.get("doc_meta") or {}).get("product_name")),
            None,
        )
        structure_directive = ""
        if product_meta:
            structure_directive = (
                "本问题涉及具体金融产品，请尽量按以下结构组织回答（仅输出有资料支撑的段落，"
                "资料未提及的字段直接写明「资料未提及」，禁止编造）：\n"
                "## 一、基本信息（产品名称/代码/类型/风险等级/发行/存续等）\n"
                "## 二、投资范围与风险揭示（投资方向、主要风险、适合的投资者）\n"
                "## 三、费用与交易规则（申购赎回、费率、起购金额、开放日等）\n"
                "## 四、适配人群与来源（适用客户、信息来源文件与时间）\n"
            )
        # FR-QA-02：问题类型引导（不改变检索路径，仅影响组织风格）
        q_type = _classify_query_type(user_query)
        type_directive = f"（问题类型：{q_type}）{_TYPE_GUIDANCE.get(q_type, '')}\n"

        prompt = (
            "你是企业知识库助手，请严格基于以下【检索资料】回答用户问题。"
            "若资料中没有相关信息，请如实说明无法回答，不要编造。"
            "不要主动引入内部资料以外的未经验证信息。\n"
            f"{external_directive}"
            f"{type_directive}"
            f"{structure_directive}\n"
            f"【检索资料】\n{context}\n\n"
            f"【用户问题】\n{user_query}"
        )

    # 支持前端指定对话模型（state.model），为空则用默认模型
    selected_model = state.get("model") or None
    model = llm_provider.chat(model=selected_model)
    full = []
    try:
        for chunk in model.stream(prompt):
            delta = getattr(chunk, "content", "") or ""
            if not delta:
                continue
            full.append(delta)
    except Exception as e:
        logger.warning(f"LLM 流式生成失败，尝试非流式兜底: {e}")
        resp = model.invoke(prompt)
        full.append(getattr(resp, "content", "") or "")

    raw_output = "".join(full)
    # 合规护栏（精卫守正）：硬校验输出，违规拦截 + 风险提示 + AI 生成标识（FR-COMP-01~04）。
    # 先完成完整生成再做合规后处理，避免把违规片段以 delta 流式泄露给前端。
    output = apply_compliance(raw_output)
    # 参考了外网来源时，追加「以官方渠道为准」提示（FR-QA-06）。
    if has_external and EXTERNAL_SOURCE_NOTE not in output:
        output = f"{output}\n\n{EXTERNAL_SOURCE_NOTE}"
    logger.info(f"LLM 作答完成，长度 {len(output)}（合规后处理：{output != raw_output}）")
    citations = _build_citations(reranked)
    if need_stream:
        _stream_text(session_id, output, need_stream, mock=False)
    return {"llm_output": output, "citations": citations}
