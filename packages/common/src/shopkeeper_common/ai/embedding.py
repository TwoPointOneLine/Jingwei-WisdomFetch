"""
BGE-M3 向量化封装。

封装 FlagEmbedding 的 BGEM3FlagModel，提供 embed_documents / embed_query，
返回稠密向量 + 稀疏向量（混合检索所需）。底层模型单例懒加载。
"""
from typing import Any

from shopkeeper_common.config.embedding_config import embedding_config
from shopkeeper_common.logging import logger


class BGEM3Embedder:
    """BGE-M3 混合向量模型封装。"""

    _model: Any = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            from FlagEmbedding import BGEM3FlagModel

            use_fp16 = embedding_config.bge_fp16
            logger.info(
                f"初始化 BGE-M3 模型: path={embedding_config.bge_m3_path or 'remote(BAAI/bge-m3)'}, "
                f"device={embedding_config.bge_device}, fp16={use_fp16}"
            )
            if embedding_config.bge_m3_path:
                cls._model = BGEM3FlagModel(
                    model_name_or_path=embedding_config.bge_m3_path,
                    use_fp16=use_fp16,
                    devices=[embedding_config.bge_device],
                )
            else:
                cls._model = BGEM3FlagModel(
                    model_name_or_path="BAAI/bge-m3",
                    use_fp16=use_fp16,
                    devices=[embedding_config.bge_device],
                )
            logger.success("BGE-M3 模型初始化成功")
        return cls._model

    @classmethod
    def _to_sparse_list(cls, sparse_dict) -> list[dict]:
        """FlagEmbedding 返回的稀疏向量是 {idx: weight} 字典，转为 Milvus 需要的列表形式。"""
        return [{"id": int(k), "weight": float(v)} for k, v in sparse_dict.items()]

    @classmethod
    def embed_documents(cls, texts: list[str]) -> dict:
        """
        批量向量化文档。
        返回 {"dense": [[...], ...], "sparse": [[{"id","weight"}, ...], ...]}
        """
        model = cls._get_model()
        out = model.encode(texts, return_dense=True, return_sparse=True, return_colbert=False)
        dense = out["dense"]
        sparse = [cls._to_sparse_list(s) for s in out["sparse"]]
        return {"dense": dense, "sparse": sparse}

    @classmethod
    def embed_query(cls, text: str) -> dict:
        """向量化单条查询（语义与文档对齐）。"""
        return cls.embed_documents([text])


# 全局便捷入口
def embed_documents(texts: list[str]) -> dict:
    return BGEM3Embedder.embed_documents(texts)


def embed_query(text: str) -> dict:
    return BGEM3Embedder.embed_query(text)
