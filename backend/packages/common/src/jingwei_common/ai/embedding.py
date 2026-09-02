"""
BGE-M3 向量化封装。

支持两种后端，由配置 BGE_M3 决定：
- local：封装 FlagEmbedding 的 BGEM3FlagModel，提供稠密 + 稀疏混合向量。
- ollama：通过本地 Ollama 的 /api/embed 接口出稠密向量（BGE-M3 在 Ollama
  中以 embedding 类型提供，默认仅返回稠密向量；稀疏向量置空，混合检索降级为稠密）。
"""
from typing import Any

import requests

from jingwei_common.ai._flagembedding_compat import ensure_flagembedding_importable
from jingwei_common.config.embedding_config import embedding_config
from jingwei_common.logging import logger


class BGEM3Embedder:
    """BGE-M3 混合向量模型封装（local 后端）。"""

    _model: Any = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            ensure_flagembedding_importable()
            from FlagEmbedding.inference.embedder.encoder_only import BGEM3FlagModel

            use_fp16 = embedding_config.bge_fp16
            from pathlib import Path

            model_name = (
                Path(embedding_config.bge_m3_path).name
                if embedding_config.bge_m3_path
                else "remote(BAAI/bge-m3)"
            )
            logger.info(
                "初始化 BGE-M3 模型: 模型=%s, 设备=%s, fp16=%s",
                model_name,
                embedding_config.bge_device,
                use_fp16,
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
        批量向量化文档（local 后端，含稠密 + 稀疏）。
        返回 {"dense": [[...], ...], "sparse": [[{"id","weight"}, ...], ...]}
        """
        model = cls._get_model()
        out = model.encode(texts, return_dense=True, return_sparse=True, return_colbert_vecs=False)
        # FlagEmbedding 1.3.x 返回键为 dense_vecs / lexical_weights
        dense = out["dense_vecs"]
        sparse = [cls._to_sparse_list(s) for s in out["lexical_weights"]]
        return {"dense": dense, "sparse": sparse}

    @classmethod
    def embed_query(cls, text: str) -> dict:
        """向量化单条查询（语义与文档对齐）。"""
        return cls.embed_documents([text])


class OllamaEmbedder:
    """通过本地 Ollama /api/embed 出稠密向量的封装（ollama 后端）。"""

    @classmethod
    def _post_embed(cls, texts: list[str]) -> list[list[float]]:
        url = f"{embedding_config.ollama_base_url.rstrip('/')}/api/embed"
        payload = {
            "model": embedding_config.ollama_bge_m3_model,
            "input": texts,
        }
        logger.info(
            f"Ollama 向量化: url={url}, model={embedding_config.ollama_bge_m3_model}, "
            f"num_texts={len(texts)}"
        )
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError(f"Ollama /api/embed 未返回 embeddings: {data}")
        return embeddings

    @classmethod
    def embed_documents(cls, texts: list[str]) -> dict:
        """
        批量向量化文档（ollama 后端，仅稠密；稀疏置空）。
        返回 {"dense": [[...], ...], "sparse": [[], ...]}（sparse 与 dense 等长，
        每项为空列表，供写入 Milvus 时空稀疏向量，并避免 zip 截断）。
        """
        dense = cls._post_embed(texts)
        # Ollama BGE-M3 默认不返回稀疏向量，混合检索降级为稠密
        sparse = [[] for _ in texts]
        return {"dense": dense, "sparse": sparse}

    @classmethod
    def embed_query(cls, text: str) -> dict:
        """向量化单条查询。"""
        return cls.embed_documents([text])


# ── 统一分发入口 ──────────────────────────────────────────────
def _embedder():
    return OllamaEmbedder if embedding_config.use_ollama else BGEM3Embedder


def embed_documents(texts: list[str]) -> dict:
    return _embedder().embed_documents(texts)


def embed_query(text: str) -> dict:
    return _embedder().embed_query(text)
