"""验证 query-server 无检索上下文时是否直接调用 LLM 回答（不再返回硬编码降级提示）。"""
from __future__ import annotations

import sys
import time
import uuid

import requests

BASE = "http://127.0.0.1:8082"
QUERY = "你是谁"
OLD_FALLBACK = "知识库暂未收录与您问题相关的资料"


def main() -> int:
    session_id = str(uuid.uuid4())
    resp = requests.post(
        f"{BASE}/chat/query",
        json={
            "session_id": session_id,
            "query": QUERY,
            "need_stream_output": False,
        },
        timeout=10,
    )
    print(f"POST /chat/query status: {resp.status_code}")
    print(resp.json())
    task_id = resp.json().get("data", {}).get("task_id")
    if not task_id:
        print("[FAIL] 未获取到 task_id")
        return 1

    answer = ""
    for i in range(30):
        time.sleep(1)
        r = requests.get(f"{BASE}/task/result/{task_id}", timeout=10)
        data = r.json().get("data", {})
        # Windows cmd 默认 GBK，emoji 会抛编码错误，转成 ASCII 安全输出
        safe_data = str(data).encode("ascii", "replace").decode("ascii")
        print(f"  poll {i+1}: {safe_data}")
        answer = data.get("llm_output", "")
        if answer:
            break
    else:
        print("[FAIL] 30s 内未拿到结果")
        return 1

    safe_answer = answer.encode("ascii", "replace").decode("ascii")
    print(f"\n最终答案: {safe_answer!r}")
    if OLD_FALLBACK in answer:
        print("[FAIL] 仍然返回了旧版硬编码降级提示")
        return 1
    print("[OK] 已正常走 LLM 回答")
    return 0


if __name__ == "__main__":
    sys.exit(main())
