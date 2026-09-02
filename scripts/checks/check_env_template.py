"""校验唯一 env 模板 deploy/env/.env.example 的质量。

检查项：
1. 无重复键（dotenv 后者覆盖前者，重复会导致配置静默失效）
2. 模板中声明的每个键都能在代码中找到读取点（避免保留死变量）
3. 代码中读取的关键键都被模板覆盖（避免配置缺失）
"""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATE = Path("deploy/env/.env.example")
# 代码根目录
CODE_DIRS = [
    Path("backend/packages/common/src"),
    Path("backend/services"),
    Path("backend/scripts"),
]
# 这些键由 Docker/compose 注入或仅在特定场景使用，不要求在代码中出现
ALLOW_UNUSED = {
    # 由 Docker compose 通过 ${VAR} 注入容器，代码中不直接读取
    "CONTAINER_BGE_M3_PATH",
    "CONTAINER_BGE_RERANKER_LARGE",
    "BGE_MODELS_DIR",
    "MONGO_USER",
    "MONGO_PASSWORD",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "GATEWAY_AUTH_HOST",
    "GATEWAY_USER_HOST",
    "GATEWAY_IMPORT_HOST",
    "GATEWAY_QUERY_HOST",
    # 用 os.environ.get 读取（非 env_str），脚本模式未覆盖
    "AUTH_BOOTSTRAP_ADMIN",
    # 可选：仅独立 wheel 安装时需要，默认注释掉
    "JINGWEI_ROOT",
}


def template_keys(path: Path) -> tuple[list[str], list[str]]:
    """返回 (全部键按出现顺序, 重复键列表)。"""
    keys: list[str] = []
    dupes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.partition("=")[0].strip()
        if key in keys:
            dupes.append(key)
        else:
            keys.append(key)
    return keys, dupes


def code_env_keys() -> set[str]:
    """扫描代码中 env_str/env_bool/env_int/os.getenv 读取的键名。"""
    pattern = re.compile(
        r"""(?:env_str|env_bool|env_int)\s*\(\s*["']([A-Z0-9_]+)["']"""
        r"""|os\.getenv\s*\(\s*["']([A-Z0-9_]+)["']"""
    )
    found: set[str] = set()
    for base in CODE_DIRS:
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            try:
                text = py.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for m in pattern.finditer(text):
                found.add(m.group(1) or m.group(2))
    return found


def main() -> int:
    if not TEMPLATE.exists():
        print(f"FAIL: template not found: {TEMPLATE}")
        return 1

    keys, dupes = template_keys(TEMPLATE)
    print(f"TEMPLATE: {TEMPLATE}   keys = {len(keys)}")

    ok = True
    print("\n[1] duplicate keys (would silently override)")
    if dupes:
        for d in dupes:
            print(f"  [DUPLICATE] {d}")
        ok = False
    else:
        print("  NONE")

    code_keys = code_env_keys()
    tpl_set = set(keys)

    print("\n[2] keys in template but never read by code (dead variables)")
    dead = sorted(k for k in tpl_set - code_keys if k not in ALLOW_UNUSED)
    if dead:
        for k in dead:
            print(f"  [DEAD] {k}")
    else:
        print("  NONE")

    print("\n[3] keys read by code but missing from template")
    missing = sorted(k for k in code_keys - tpl_set)
    if missing:
        for k in missing:
            print(f"  [MISSING] {k}")
    else:
        print("  NONE")

    print(f"\nRESULT: {'PASS' if ok and not dead else 'WARN'}"
          f"{'' if not missing else ' (missing keys are usually app defaults)'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
