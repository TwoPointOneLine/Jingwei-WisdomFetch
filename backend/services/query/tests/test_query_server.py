"""智能问答服务冒烟测试：FastAPI 应用可加载、关键路由就位。"""


def test_app_imports():
    from jingwei_query.api.query_server.main import app

    assert app is not None
    paths = {r.path for r in app.routes}
    assert "/chat/query" in paths
    assert "/models" in paths
    assert "/chat/stream/{session_id}" in paths
    assert "/task/result/{task_id}" in paths
    assert "/sessions" in paths
    assert "/health" in paths


def test_query_chain_importable():
    from jingwei_query.process.query_chain.main_graph import kb_query_app
    from jingwei_query.process.query_chain.state import _last_write_wins

    assert kb_query_app is not None
    assert callable(_last_write_wins)


def test_rag_core_importable():
    from jingwei_query.rag.query import (
        fuse_by_rrf,
        llm_answer,
        vector_retrieve,
        web_search,
    )

    assert callable(llm_answer)
    assert callable(fuse_by_rrf)
    assert callable(vector_retrieve)
    assert callable(web_search)


def test_infra_importable():
    from jingwei_query.infra.mcp import search_web_documents
    from jingwei_query.infra.persistence import history_repo, persistence

    assert history_repo is not None
    assert persistence is not None
    assert callable(search_web_documents)
