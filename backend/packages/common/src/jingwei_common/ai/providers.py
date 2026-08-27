"""
LLM 统一出口（门面）。

业务/节点层统一通过 `llm_provider` 访问：
- embed_documents / embed_query  （向量化）
- reranker_model                 （重排序）
- chat / vl_chat                 （对话模型）

屏蔽底层模型加载细节（BGE-M3 / BGE-Reranker / DashScope）。
"""
from jingwei_common.ai.chat import chat, vl_chat
from jingwei_common.ai.embedding import embed_documents, embed_query
from jingwei_common.ai.reranker import BGEReranker


class LLMProvider:
    """统一模型出口。"""

    def embed_documents(self, texts: list[str]) -> dict:
        return embed_documents(texts)

    def embed_query(self, text: str) -> dict:
        return embed_query(text)

    def reranker_model(self):
        return BGEReranker.get_model()

    def compute_rerank_score(self, pairs: list[list[str]], normalize: bool = True) -> list[float]:
        return BGEReranker.compute_score(pairs, normalize=normalize)

    def chat(self, model: str | None = None):
        return chat(model)

    def vl_chat(self):
        return vl_chat()


llm_provider = LLMProvider()
