"""仓库整洁性契约检查（一次性运行全部校验）。

背景：本仓库曾出现"门禁失效但无人察觉"的情况——CI 三个 job 在错误目录执行、
CD 引用的 Dockerfile 路径不存在，两者长期静默失败。为避免整洁性再次腐化，
把关键不变量固化为可自动执行的检查。

用法（在仓库根执行）：
    python scripts/checks/run_all.py

退出码：全部通过返回 0；任一失败返回 1（可直接接入 CI）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECKS = [
    ("Dockerfile COPY 源路径存在于构建上下文", ["check_dockerfiles.py"]),
    ("env 模板质量（无重复键/无死变量）", ["check_env_template.py"]),
    ("构建上下文关键文件未被 .dockerignore 误排除", ["measure_context.py", ".", "--verify"]),
]

HERE = Path(__file__).resolve().parent


def main() -> int:
    failed = 0
    for title, args in CHECKS:
        print("=" * 66)
        print(f"[CHECK] {title}")
        print("=" * 66)
        r = subprocess.run(
            [sys.executable, str(HERE / args[0]), *args[1:]],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        out = (r.stdout or "").strip()
        if out:
            print(out)
        if r.returncode != 0:
            failed += 1
            err = (r.stderr or "").strip()
            if err:
                print(err)
            print(f"  -> FAILED (exit={r.returncode})")
        else:
            print("  -> PASSED")
        print()

    print("=" * 66)
    if failed:
        print(f"RESULT: {failed} check(s) FAILED")
        return 1
    print(f"RESULT: all {len(CHECKS)} checks PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
