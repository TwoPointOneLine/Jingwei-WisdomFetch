"""
LLM 作答服务（RAG 生成）：基于重排后的上下文生成答案，支持流式增量推送（SSE）。

依赖：
  - 重排后的 rerank_documents 作为上下文；
  - 通过 delta_queue / SSE 把生成内容逐字推送给前端。
无检索上下文时优雅降级为友好提示。
"""
import time

from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.config.lm_config import lm_config
from shopkeeper_common.logging import logger
from shopkeeper_common.web.sse_utils import push_to_session

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
        _stream_text(session_id, mock_text, need_stream, mock=True)
        return {"llm_output": mock_text}

    # 无检索上下文时的优雅降级：返回友好提示（模拟流式逐字推送，保证前端有打字机效果）
    if not reranked:
        logger.warning("无检索上下文，返回降级提示（知识库未收录/向量模型未就绪）")
        degraded = (
            "知识库暂未收录与您问题相关的资料，或未成功建立向量索引。"
            "请先导入并索引相关文档，或检查向量模型配置后重试。"
        )
        _stream_text(session_id, degraded, need_stream)
        return {"llm_output": degraded}

    context = _format_context(reranked)

    prompt = (
        "你是企业知识库助手，请严格基于以下【检索资料】回答用户问题。"
        "若资料中没有相关信息，请如实说明无法回答，不要编造。\n\n"
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
            if need_stream:
                push_to_session(session_id, "delta", {"text": delta})
    except Exception as e:
        logger.warning(f"LLM 流式生成失败，尝试非流式兜底: {e}")
        resp = model.invoke(prompt)
        full.append(getattr(resp, "content", "") or "")

    output = "".join(full)
    logger.info(f"LLM 作答完成，长度 {len(output)}")
    return {"llm_output": output}
