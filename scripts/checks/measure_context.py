"""按 .dockerignore 规则统计构建上下文的文件数与字节数（确定性度量）。

用途：对比加/不加 .dockerignore 时发送给 Docker 守护进程的上下文规模。
相比 `docker build` 观察传输量，本脚本不受 BuildKit 文件缓存影响，结果可复现。

用法：
    python temp/measure_context.py backend            # 应用 backend/.dockerignore
    python temp/measure_context.py backend --no-ignore # 忽略规则，统计全量
"""
from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path


def load_patterns(dockerignore: Path) -> list[str]:
    """解析 .dockerignore，忽略空行与注释。"""
    if not dockerignore.exists():
        return []
    patterns = []
    for line in dockerignore.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def build_matchers(patterns: list[str]):
    """返回 (目录名集合, 文件名模式集合)。

    简化实现：仅支持 .dockerignore 中最常用的两种形式，
    足以覆盖本项目 backend/.dockerignore 的全部规则。
    """
    dirs: set[str] = set()
    globs: list[str] = []
    for p in patterns:
        norm = p.lstrip("/").rstrip("/")
        if not norm:
            continue
        if "/" in norm:
            # 形如 **/__pycache__、logs/、dist
            globs.append(norm)
        else:
            # 无斜杠项可能是目录名（.venv）或文件名通配（*.pyc）
            if "*" in norm:
                globs.append(norm)
            else:
                dirs.add(norm)
    return dirs, globs


def is_ignored(rel_parts: tuple[str, ...], dirs: set[str], globs: list[str]) -> bool:
    """判断相对路径是否被忽略。

    支持三种 .dockerignore 形式（覆盖本仓库全部规则）：
      1) 目录名（无斜杠）：.venv、logs、docs —— 匹配任意层级下的该目录及其内容
      2) 相对路径模式（含斜杠）：frontend/node_modules、backend/logs
         —— 匹配该路径本身及其下所有内容（相对上下文根）
      3) 通配：**/__pycache__、*.pyc
    """
    rel = "/".join(rel_parts)

    # 1) 目录名：路径中任一层级命中即忽略（含该目录自身及其内容）
    for part in rel_parts:
        if part in dirs:
            return True

    for g in globs:
        # 3) 通配：含 * 的模式按 fnmatch 匹配完整相对路径
        if "*" in g:
            if fnmatch.fnmatch(rel, g):
                return True
            if g.startswith("**/") and fnmatch.fnmatch(rel_parts[-1], g[3:]):
                return True
            continue
        # 2) 相对路径模式：命中该路径本身或其下任意内容
        if rel == g or rel.startswith(g.rstrip("/") + "/"):
            return True
    return False


# Dockerfile 中 COPY 的每一项都必须保留在上下文内，否则构建会失败。
# 阶段 3 方案 B 后构建上下文 = 仓库根，故路径均以 backend/ 开头。
CRITICAL_FILES = [
    "backend/pyproject.toml",
    "backend/README.md",
    "backend/uv.lock",
    "backend/packages/common/pyproject.toml",
    "backend/services/gateway/pyproject.toml",
    "backend/services/auth/pyproject.toml",
    "backend/services/user/pyproject.toml",
    "backend/services/knowledge/pyproject.toml",
    "backend/services/query/pyproject.toml",
    "backend/packages/common/src/jingwei_common/clients/mongo_history_utils.py",
    "backend/services/query/src/jingwei_query/api/query_server/main.py",
]

# 这些必须被排除，否则上下文体积与镜像层缓存都会受影响。
MUST_EXCLUDE_DIRS = [".venv", "backend/.venv", "frontend/node_modules", "frontend/dist"]


def verify(root: Path) -> int:
    """校验：关键文件未被误排除 + 大目录确已排除。"""
    patterns = load_patterns(root / ".dockerignore")
    dirs, globs = build_matchers(patterns)

    wrongly_ignored = [
        f for f in CRITICAL_FILES
        if is_ignored(tuple(f.split("/")), dirs, globs)
    ]
    missing = [f for f in CRITICAL_FILES if not (root / f).exists()]

    print(f"CRITICAL FILES ({len(CRITICAL_FILES)} checked)")
    print(f"  wrongly ignored : {wrongly_ignored or 'NONE'}")
    print(f"  missing on disk : {missing or 'NONE'}")
    print("MUST-EXCLUDE DIRS")
    # 用 is_ignored 判断该目录下任意文件是否被忽略（比只看 dirs 集合准确）
    for d in MUST_EXCLUDE_DIRS:
        exists = (root / d).exists()
        excluded = exists and is_ignored(
            tuple(d.split("/")) + ("probe.txt",), dirs, globs
        )
        print(f"  {d:<22} exists={exists!s:<5} excluded={excluded}")

    ok = not wrongly_ignored and not missing
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1]).resolve()
    if "--verify" in sys.argv:
        return verify(root)
    use_ignore = "--no-ignore" not in sys.argv

    mib = 1024 * 1024

    def scan(apply_ignore: bool) -> tuple[int, int]:
        """遍历上下文目录，返回 (文件数, 字节数)。"""
        patterns = load_patterns(root / ".dockerignore") if apply_ignore else []
        dirs, globs = build_matchers(patterns)
        files = size = 0
        for dirpath, dirnames, filenames in os.walk(root):
            cur = Path(dirpath)
            rel_dir = cur.relative_to(root)
            rel_dir_parts = () if str(rel_dir) == "." else rel_dir.parts

            # 被忽略的目录整棵剪枝（不再下钻，故 total 不能用它做基准）
            if apply_ignore:
                dirnames[:] = [
                    d for d in dirnames
                    if d not in dirs
                    and not is_ignored(rel_dir_parts + (d, "\0"), dirs, globs)
                ]

            for name in filenames:
                try:
                    fsize = (cur / name).stat().st_size
                except OSError:
                    continue
                if apply_ignore and is_ignored(rel_dir_parts + (name,), dirs, globs):
                    continue
                files += 1
                size += fsize
        return files, size

    patterns = load_patterns(root / ".dockerignore")
    if use_ignore:
        sent_files, sent_bytes = scan(True)
        all_files, all_bytes = scan(False)
        print(f"context = {root}   规则数 = {len(patterns)}")
        print(f"  全量（无 .dockerignore）: {all_files:>6} 文件 / {all_bytes / mib:>8.1f} MiB")
        print(f"  应用 .dockerignore     : {sent_files:>6} 文件 / {sent_bytes / mib:>8.1f} MiB")
        print(f"  排除                   : {all_files - sent_files:>6} 文件 / "
              f"{(all_bytes - sent_bytes) / mib:>8.1f} MiB")
    else:
        all_files, all_bytes = scan(False)
        print(f"context = {root}   （未应用 .dockerignore）")
        print(f"  全量: {all_files} 文件 / {all_bytes / mib:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
