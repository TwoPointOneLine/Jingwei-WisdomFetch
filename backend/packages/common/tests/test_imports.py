"""公共模块可导入性测试（不触发外部连接，模型/客户端均懒加载）。"""


def test_import_subpackages():
    import jingwei_common
    import jingwei_common.ai
    import jingwei_common.clients
    import jingwei_common.config
    import jingwei_common.constants
    import jingwei_common.logging
    import jingwei_common.protocols
    import jingwei_common.utils
    import jingwei_common.web
    from jingwei_common.ai import llm_provider
    from jingwei_common.clients import milvus_client, minio_client, mongo_client
    from jingwei_common.config import infra_config

    assert jingwei_common.__version__
    assert infra_config.app
    assert llm_provider
    assert mongo_client and milvus_client and minio_client


def test_import_common_names():
    from jingwei_common.logging import logger
    from jingwei_common.protocols import ApiError
    from jingwei_common.utils import chunk_text, md5, safe_get
    from jingwei_common.web import ApiResponse, ok

    assert logger
    assert callable(md5)
    assert callable(chunk_text)
    assert callable(safe_get)
    assert callable(ApiResponse.ok)
    assert callable(ok)
    assert ApiError
