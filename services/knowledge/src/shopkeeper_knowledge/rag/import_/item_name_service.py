"""
主体识别服务：从文档切片中识别商品/资料主体名称（item_name）。

利用 LLM 从标题与正文抽取规范的 item_name，并写入 MongoDB 主体索引，
供查询阶段主体确认使用。LLM 不可用时回退为 file_title。
"""
from shopkeeper_common.ai.providers import llm_provider
from shopkeeper_common.config.providers import infra_config
from shopkeeper_common.logging import logger

from shopkeeper_knowledge.infra.persistence.mongo_store import persistence

# 主体索引集合名（与 item_store 对应）
_ITEM_COLLECTION = infra_config.milvus.item_name_collection


def recognize_and_index_item_name(state) -> dict:
    """
    从 state.chunks / file_title 识别 item_name，写库后回写 item_name。
    """
    chunks = state.get("chunks") or []
    file_title = state.get("file_title", "")

    # 取前若干 chunk 作为识别语料
    sample = "\n".join(c.get("content", "") for c in chunks[:3])[:1500]
    prompt = (
        "请从下面的资料中识别它描述的『主体名称』（商品型号、设备名称或资料主题），"
        "只返回一个简洁规范的名称，不要解释。\n\n"
        f"文件名：{file_title}\n资料片段：\n{sample}"
    )

    item_name = file_title
    try:
        model = llm_provider.chat()
        resp = model.invoke(prompt)
        text = (getattr(resp, "content", "") or "").strip()
        if text:
            item_name = text
    except Exception as e:
        logger.warning(f"主体识别失败，回退 file_title: {e}")

    # 写主体索引（便于查询侧主体确认）
    try:
        persistence.update_one(
            _ITEM_COLLECTION,
            {"item_name": item_name},
            {"$set": {"file_title": file_title, "item_name": item_name}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"主体索引写入失败（不影响主流程）: {e}")

    logger.info(f"主体识别: {file_title} -> {item_name}")
    return {"item_name": item_name}
