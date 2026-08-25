"""公共模块运行自检（smoke test）。

用法：
    cd packages/common && uv run python scripts/smoke.py

验证公共模块各子包可正常导入并返回合理值。
"""
from __future__ import annotations

import shopkeeper_common
from shopkeeper_common.ai import list_models, llm_provider
from shopkeeper_common.clients import (
    milvus_client,
    minio_client,
    mongo_client,
)
from shopkeeper_common.clients.mongo_client import MONGO_DB_NAME, MONGO_URL
from shopkeeper_common.config import infra_config
from shopkeeper_common.config.common import PROJECT_ROOT
from shopkeeper_common.constants import (
    CODE_OK,
    COLLECTION_SESSIONS,
    SSE_EVENT_DELTA,
    TASK_STATUS_ORDER,
)
from shopkeeper_common.logging import logger
from shopkeeper_common.utils import chunk_text, clean_text, md5, safe_get
from shopkeeper_common.utils.prompt_utils import load_prompt
from shopkeeper_common.web import (
    ApiError,
    ApiResponse,
    SSEEvent,
    create_sse_queue,
    fail,
    get_sse_queue,
    ok,
    push_to_session,
)


def main() -> None:
    logger.info("公共模块运行自检开始")
    print("=" * 56)

    # 1) 版本与项目根
    print(f"{'version':<16}: {shopkeeper_common.__version__}")
    print(f"{'PROJECT_ROOT':<16}: {PROJECT_ROOT}")

    # 2) 配置门面
    print(f"{'llm.provider':<16}: {infra_config.llm.provider}")
    print(f"{'milvus':<16}: {infra_config.milvus.milvus_url}")
    print(f"{'mongo':<16}: {MONGO_URL} / db={MONGO_DB_NAME}")
    print(f"{'minio':<16}: {infra_config.minio.endpoint}")
    print(
        f"{'mineru':<16}: {getattr(infra_config.mineru, 'api_url', None) or getattr(infra_config.mineru, 'base_url', None)}"
    )

    # 3) 常量
    print(f"{'TASK_STATUS_ORDER':<16}: {TASK_STATUS_ORDER}")
    print(f"{'CODE_OK':<16}: {CODE_OK}, SSE_EVENT_DELTA={SSE_EVENT_DELTA}, {COLLECTION_SESSIONS}")

    # 4) 工具函数
    print(f"{'md5(hello)':<16}: {md5('hello')}")
    chunks = chunk_text("掌柜智库公共模块运行自检。" * 20, size=200, overlap=50)
    print(f"{'chunk_text':<16}: {len(chunks)} chunks -> {chunks[0][:20]}...")
    cleaned = clean_text("  你好\n世界  ")
    print(f"{'clean_text':<16}: {cleaned!r}")
    print(f"{'safe_get':<16}: {safe_get({'a': {'b': 1}}, 'a.b')}")

    # 5) 提示词资源
    prompt = load_prompt("import_intent")
    print(f"{'load_prompt':<16}: {len(prompt)} chars -> {prompt[:28]}...")

    # 6) 统一响应与异常
    print(f"{'ApiResponse.ok':<16}: {ApiResponse.ok(data={'task_id': 'abc'})}")
    print(f"{'ok / fail':<16}: code={ok(message='done')['code']} / code={fail(400, 'oops')['code']}")
    try:
        raise ApiError(message="演示异常")
    except ApiError as e:
        print(f"{'ApiError':<16}: {e.code} {e.message}")

    # 7) SSE 事件队列
    create_sse_queue("smoke-demo")
    push_to_session("smoke-demo", SSEEvent.DELTA, {"answer": "测试增量"})
    pushed = get_sse_queue("smoke-demo").get(timeout=1)
    print(f"{'SSE push':<16}: {pushed}")

    # 8) AI 统一出口与懒加载客户端（仅确认可实例化，不发起真实连接）
    print(f"{'llm_provider':<16}: {type(llm_provider).__name__}")
    print(f"{'list_models()':<16}: {list_models()}")
    print(f"{'mongo_client':<16}: {type(mongo_client).__name__}")
    print(f"{'milvus_client':<16}: {type(milvus_client).__name__}")
    print(f"{'minio_client':<16}: {type(minio_client).__name__}")

    logger.info("公共模块运行自检通过")
    print("=" * 56)
    print("ALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
