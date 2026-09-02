"""静态校验：各 Dockerfile 中 COPY 的源路径在构建上下文内必须存在。

阶段 3 方案 B 后：构建上下文 = 仓库根，Dockerfile 位于 deploy/docker/。
COPY 引用了不存在的文件会导致构建直接失败，
本脚本在不触发真实构建（耗时长）的前提下提前发现这类问题。
"""
from __future__ import annotations

import re
from pathlib import Path

# 构建上下文 = 仓库根（与 deploy/compose.yml 的 build.context: .. 一致）
CONTEXT = Path(".").resolve()
DOCKERFILES = sorted(Path("deploy/docker").glob("*.Dockerfile"))

# 匹配 COPY 指令，取 --from 之后（如有）到目标路径之前的源路径部分
COPY_RE = re.compile(r"^\s*COPY\s+(.*?)\s+(\S+)\s*$", re.M)


def main() -> int:
    problems: list[str] = []
    for df in DOCKERFILES:
        text = df.read_text(encoding="utf-8")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("COPY") or "--from=" in line:
                continue
            match = COPY_RE.match(raw_line)
            if not match:
                continue
            sources_part, _dest = match.group(1), match.group(2)
            sources = sources_part.split()
            if len(sources) < 1:
                continue
            for src in sources:
                src_path = src.lstrip("/")
                if any(ch in src_path for ch in "*?["):
                    continue  # 通配，跳过
                target = CONTEXT / src_path
                if target.exists():
                    continue
                # 若上下文中不存在，但该文件由同 Dockerfile 更早的 COPY 创建，也算合法
                problems.append(f"{df.name}: COPY 源不存在 -> {src_path}")
    if problems:
        print("PROBLEMS FOUND:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"CHECKED {len(DOCKERFILES)} Dockerfiles, all COPY sources exist in context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
