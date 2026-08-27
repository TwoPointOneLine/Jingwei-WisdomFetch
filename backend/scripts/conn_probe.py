"""外部依赖连通性探针（本地调试用）。

验证三类外部联通性：
1. LLM（DashScope 兼容 OpenAI 协议）—— 最关键，确认外部模型可达
2. Milvus 向量库
3. MongoDB 持久化

用法（项目根目录，已激活 venv 环境）：
    python scripts/conn_probe.py
"""
from __future__ import annotations

import os
import sys
import time

# 让脚本能在项目根目录直接 import jingwei_common
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packages", "common", "src"))

# 加载 .env（与项目其他模块一致，优先本地 .env）
def _load_env() -> None:
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            os.environ.setdefault(k, v)


_load_env()


def _banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_llm() -> bool:
    _banner("1. LLM（DashScope 兼容 OpenAI 协议）")
    try:
        from jingwei_common.config import lm_config
        from langchain_openai import ChatOpenAI
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 导入依赖失败: {e}")
        return False

    print(f"  provider     : {lm_config.provider}")
    print(f"  base_url     : {lm_config.active_base_url}")
    print(f"  model        : {lm_config.active_default_model}")
    key = lm_config.active_api_key
    print(f"  api_key      : {'*' * 6 + key[-4:] if key else '(空)'}")

    if not key or key in ("your_dashscope_api_key",):
        print("  [WARN] API Key 未配置或为占位符，跳过真实调用")
        return False

    try:
        chat = ChatOpenAI(
            model=lm_config.active_default_model,
            api_key=key,
            base_url=lm_config.active_base_url,
            temperature=0.1,
            max_retries=1,
            timeout=30,
        )
        t0 = time.time()
        resp = chat.invoke("用一句话回复：ping")
        cost = time.time() - t0
        print(f"  [OK] 响应耗时 {cost:.2f}s")
        content = getattr(resp, "content", "") or ""
        # Windows 控制台为 GBK，emoji/特殊字符会抛 UnicodeEncodeError，做安全转义
        safe = content.encode("ascii", "replace").decode("ascii")
        print(f"  回复内容     : {safe[:120]!r}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 调用失败: {type(e).__name__}: {e}")
        return False


def test_milvus() -> bool:
    _banner("2. Milvus 向量库")
    try:
        from jingwei_common.config import milvus_config
        from pymilvus import MilvusClient
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 导入依赖失败: {e}")
        return False

    url = milvus_config.milvus_url
    print(f"  milvus_url   : {url}")
    try:
        t0 = time.time()
        client = MilvusClient(uri=url)
        # 轻量探测：列出集合（空库也返回 []）
        collections = client.list_collections()
        cost = time.time() - t0
        print(f"  [OK] 连接成功，耗时 {cost:.2f}s，集合数: {len(collections)}")
        print(f"  集合列表     : {collections}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 连接失败: {type(e).__name__}: {e}")
        return False


def test_mongo() -> bool:
    _banner("3. MongoDB 持久化")
    try:
        from jingwei_common.config import env_str
        from pymongo import MongoClient
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 导入依赖失败: {e}")
        return False

    url = env_str("MONGO_URL", "mongodb://127.0.0.1:27017")
    db = env_str("MONGO_DB_NAME", "enterprise_rag")
    # 脱敏打印
    safe = url.replace("//", "//***@") if "@" in url else url
    print(f"  mongo_url    : {safe}")
    print(f"  db_name      : {db}")
    try:
        t0 = time.time()
        client = MongoClient(url, serverSelectionTimeoutMS=5000)
        # 触发一次握手
        client.admin.command("ping")
        cost = time.time() - t0
        names = client.list_database_names()
        print(f"  [OK] 连接成功，耗时 {cost:.2f}s，可用库: {names}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 连接失败: {type(e).__name__}: {e}")
        return False


def main() -> int:
    _banner("外部依赖连通性探针")
    print(f"  root         : {ROOT}")
    print(f"  python       : {sys.executable}")

    results = {
        "LLM": test_llm(),
        "Milvus": test_milvus(),
        "MongoDB": test_mongo(),
    }

    _banner("汇总")
    ok = sum(1 for v in results.values() if v)
    for name, passed in results.items():
        print(f"  {name:<10}: {'PASS' if passed else 'FAIL'}")
    print(f"\n  通过 {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
