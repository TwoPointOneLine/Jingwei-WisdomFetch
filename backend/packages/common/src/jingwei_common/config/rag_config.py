"""RAG 检索与生成参数配置（G-10）。

背景：此前 top_k / rerank_top_k / rrf_k / history 轮数等全部硬编码在业务代码里
（embedding_search_service、hyde_search_service、rerank_service、rrf_service、
query_rewrite_service），线上调优必须改代码，且各服务取值无法统一。

本模块集中声明这些"可调优但影响效果"的参数，统一从环境变量读取。
默认值与改动前代码中的硬编码保持一致，保证行为不因重构而改变。
"""
from jingwei_common.config.common import env_bool, env_float, env_int  # noqa: F401


class RagConfig:
    # ── 召回 ────────────────────────────────────────────────
    # 单路召回返回条数（向量路 / HyDE 路各自取 top_k）
    retrieval_top_k: int = env_int("RETRIEVAL_TOP_K", 10)
    # 是否启用 HyDE（假设性文档）召回
    hyde_enabled: bool = env_bool("HYDE_ENABLED", True)

    # ── 融合 ────────────────────────────────────────────────
    # RRF 融合常数 k，越大则排名靠前的影响越小
    rrf_k: int = env_int("RRF_K", 60)

    # ── 精排 ────────────────────────────────────────────────
    # 是否启用 BGE-Reranker 精排（关闭则退化为 RRF 粗排截断）
    rerank_enabled: bool = env_bool("RERANK_ENABLED", True)
    # 精排后保留的上下文条数
    rerank_top_k: int = env_int("RERANK_TOP_K", 5)
    # 精排分数下限（0~1，normalize=True 时）；低于此值视为不相关，直接拒答。
    # 设为 0 可关闭过滤（G-05：默认 0.35，避免低相关噪声被当作依据生成回答）。
    rerank_score_threshold: float = env_float("RERANK_SCORE_THRESHOLD", 0.35)

    # ── 多轮上下文 ──────────────────────────────────────────
    # 注入作答 prompt 的历史轮数（1 轮 = 1 条 user + 1 条 assistant）
    history_turns: int = env_int("HISTORY_TURNS", 4)
    # query rewrite 阶段读取的历史条数
    rewrite_history_limit: int = env_int("REWRITE_HISTORY_LIMIT", 10)

    # ── 引用 ────────────────────────────────────────────────
    # 引用来源中原文片段的最大字符数
    citation_snippet_chars: int = env_int("CITATION_SNIPPET_CHARS", 200)

    # ── 兜底大模型 ──────────────────────────────────────────
    # 知识库无可用上下文时，是否调用外部大模型（不基于检索资料）兜底回答。
    # 默认关闭：开启后回答不再受知识库约束，可能编造，仅作最后兜底。
    # 仍经合规护栏处理，并明确标注来源为「通用大模型、非知识库资料」。
    external_fallback_enabled: bool = env_bool("EXTERNAL_FALLBACK_ENABLED", False)


rag_config = RagConfig()
