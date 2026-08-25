"""公共模块可导入性测试（不触发外部连接，模型/客户端均懒加载）。"""


def test_import_subpackages():
    import shopkeeper_common
    import shopkeeper_common.ai
    import shopkeeper_common.clients
    import shopkeeper_common.config
    import shopkeeper_common.constants
    import shopkeeper_common.logging
    import shopkeeper_common.protocols
    import shopkeeper_common.utils
    import shopkeeper_common.web
    from shopkeeper_common.ai import llm_provider
    from shopkeeper_common.clients import milvus_client, minio_client, mongo_client
    from shopkeeper_common.config import infra_config

    assert shopkeeper_common.__version__
    assert infra_config.app
    assert llm_provider
    assert mongo_client and milvus_client and minio_client


def test_import_common_names():
    from shopkeeper_common.logging import logger
    from shopkeeper_common.protocols import ApiError
    from shopkeeper_common.utils import chunk_text, md5, safe_get
    from shopkeeper_common.web import ApiResponse, ok

    assert logger
    assert callable(md5)
    assert callable(chunk_text)
    assert callable(safe_get)
    assert callable(ApiResponse.ok)
    assert callable(ok)
    assert ApiError
