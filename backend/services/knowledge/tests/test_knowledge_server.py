"""知识库导入服务冒烟测试：FastAPI 应用可加载、关键路由就位。"""


def test_app_imports():
    from jingwei_knowledge.api.import_server.main import app

    assert app is not None
    paths = {r.path for r in app.routes}
    assert "/upload" in paths
    assert "/status/{task_id}" in paths
    assert "/health" in paths


def test_import_chain_importable():
    from jingwei_knowledge.process.import_chain.main_graph import kb_import_app
    from jingwei_knowledge.process.import_chain.state import get_default_state

    assert kb_import_app is not None
    state = get_default_state()
    assert isinstance(state, dict)
    assert "task_id" in state


def test_rag_core_importable():
    from jingwei_knowledge.rag.import_ import (
        index_chunks,
        resolve_input_file,
    )

    assert callable(resolve_input_file)
    assert callable(index_chunks)
