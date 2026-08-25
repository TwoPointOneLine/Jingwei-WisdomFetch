"""
BGE-Reranker 重排序封装。

封装 FlagEmbedding 的 FlagReranker，提供单例与 rerank 打分接口。
"""
from typing import Any

from shopkeeper_common.config.reranker_config import reranker_config
from shopkeeper_common.logging import logger


class BGEReranker:
    """BGE-Reranker 重排序模型封装（单例）。"""

    _model: Any = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            from FlagEmbedding import FlagReranker

            logger.info(
                f"初始化 BGE-Reranker: path={reranker_config.bge_reranker_large}, "
                f"device={reranker_config.bge_reranker_device}, fp16={reranker_config.bge_reranker_fp16}"
            )
            cls._model = FlagReranker(
                model_name_or_path=reranker_config.bge_reranker_large,
                device=reranker_config.bge_reranker_device,
                use_fp16=reranker_config.bge_reranker_fp16,
            )
            logger.success("BGE-Reranker 初始化成功")
        return cls._model

    @classmethod
    def compute_score(cls, pairs: list[list[str]], normalize: bool = True) -> list[float]:
        """
        计算 (query, doc) 对的相关性分数。
        :param pairs: [[query, doc], ...]
        :param normalize: 是否归一化到 0~1
        :return: 分数列表
        """
        return cls.get_model().compute_score(pairs, normalize=normalize)

    @classmethod
    def tokenizer(cls):
        return cls.get_model().tokenizer
