"""阶段5：精卫一键部署与运维脚本。

用法（Windows 可直接执行 scripts\\deploy.bat，效果等同）：
    python scripts/deploy.py build                    # 构建前端 + 五服务镜像
    python scripts/deploy.py up                       # 启动全部（基础设施 + 五服务）
    python scripts/deploy.py up --services gateway,query   # 按需启停（依赖自动拉起）
    python scripts/deploy.py down                     # 停止全部
    python scripts/deploy.py down --volumes           # 停止并删除数据卷
    python scripts/deploy.py ps                       # 查看容器状态
    python scripts/deploy.py health                   # 健康检查（轮询等待就绪）
    python scripts/deploy.py logs gateway             # 查看服务日志

前置条件：
    - Docker Desktop（或 docker + compose v2）
    - 已复制 deploy/env/.env.example 为【仓库根】.env 并填入真实配置
    - 前端产物 frontend/dist 已构建（up 前会自动校验，缺失则提示执行 build）

路径约定：
    - 所有路径基准为仓库根（本文件位于 backend/scripts/，故取 parents[2]）
    - .env / frontend/dist 在仓库根；deploy/compose.yml 在仓库根 deploy/ 下
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# 本文件位于 backend/scripts/，故 parents[2] 才是仓库根（monorepo 根）。
# 注意：backend/ 是 uv workspace 根，但 .env、frontend/、deploy/ 都在仓库根，
# 路径基准必须统一为仓库根，否则 check_env / build_frontend 会指向 backend/ 下不存在的位置。
ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = str(ROOT / "deploy" / "compose.yml")
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

# 模块名 → compose 服务名
SERVICES: dict[str, str] = {
    "gateway": "gateway-server",
    "auth": "auth-server",
    "user": "user-server",
    "knowledge": "knowledge-server",
    "query": "query-server",
}

# 模块名 → 健康检查端点（宿主机端口）
HEALTH_URLS: dict[str, str] = {
    "gateway": "http://127.0.0.1:8080/health",
    "auth": "http://127.0.0.1:8083/health",
    "user": "http://127.0.0.1:8084/health",
    "knowledge": "http://127.0.0.1:8081/health",
    "query": "http://127.0.0.1:8082/health",
}


def _run(cmd: list[str], check: bool = True) -> int:
    print(f"$ {subprocess.list2cmdline(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, check=check).returncode


def _resolve_services(names: list[str]) -> list[str]:
    """解析模块名（空则全部），返回 compose 服务名列表。"""
    if not names:
        return list(SERVICES.values())
    unknown = [n for n in names if n not in SERVICES]
    if unknown:
        raise SystemExit(f"未知模块: {', '.join(unknown)}；可选: {', '.join(SERVICES)}")
    return [SERVICES[n] for n in names]


def check_docker() -> None:
    if shutil.which("docker") is None:
        raise SystemExit("未检测到 docker，请先安装 Docker Desktop 并确保 CLI 可用。")
    _run(["docker", "compose", "-f", COMPOSE_FILE, "version"])


# 9.2 弱口令 / 占位符黑名单：部署前拦截明显的示例凭据，避免生产环境用默认弱口令启动。
_WEAK_VALUES = (
    "shopkeeper123",
    "your_dashscope_api_key",
    "your_mineru_api_url",
    "change_me",
    "changeme",
    "<",
    "example",
    "placeholder",
)
# 真正承载密钥、绝不允许为占位符/弱口令的键（按前缀粗匹配即可）。
_SECRET_PREFIXES = (
    "MONGO_PASSWORD",
    "MINIO_SECRET_KEY",
    "OPENAI_API_KEY",
    "DASHSCOPE_API_KEY",
    "JWT_SECRET",
)


def check_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(
            "缺少根目录 .env 文件。请先执行：\n"
            "  Windows:  copy deploy\\env\\.env.example .env\n"
            "  Linux:    cp deploy/env/.env.example .env\n"
            "然后按需修改其中的 API Key / 模型路径等配置。\n"
            "注意：位置必须是仓库根（本文件通过 env_file: [../.env] 引用）。"
        )
    # 9.2 凭据强度前置校验
    raw = env_path.read_text(encoding="utf-8", errors="ignore")
    violations: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        if any(value == w or value.lower().startswith(w) for w in _WEAK_VALUES):
            # 仅当键名属于机密类或值确属明显占位时才报错
            if any(key.startswith(p) for p in _SECRET_PREFIXES) or value in _WEAK_VALUES:
                violations.append(f"{key}={value}")
    if violations:
        raise SystemExit(
            "检测到 .env 中存在弱口令 / 未替换的占位符，禁止用于部署：\n  - "
            + "\n  - ".join(violations)
            + "\n请替换为真实强凭据后再执行部署。"
        )


def check_frontend_dist() -> None:
    """校验前端产物已构建。

    compose 以只读方式挂载仓库根 frontend/dist，目录不存在时 Docker 会静默创建空目录，
    导致网关虽 healthy 但首页 404，故障现象与根因距离过远，故在此前置拦截。
    """
    if not (FRONTEND_DIST / "index.html").exists():
        raise SystemExit(
            f"未检测到前端产物：{FRONTEND_DIST / 'index.html'}\n"
            "请先构建前端：\n"
            "  pnpm --dir frontend install && pnpm --dir frontend build\n"
            "或执行： python scripts/deploy.py build"
        )


def build_frontend() -> None:
    """构建前端 dist（gateway 通过 compose 挂载托管）。"""
    if not (FRONTEND_DIR / "package.json").exists():
        raise SystemExit(f"{FRONTEND_DIR / 'package.json'} 不存在，无法构建前端。")
    pkg = shutil.which("pnpm") or shutil.which("npm")
    if pkg is None:
        raise SystemExit("未检测到 pnpm / npm，请先安装 Node.js 工具链。")
    if Path(pkg).name.lower().startswith("pnpm"):
        _run([pkg, "--dir", str(FRONTEND_DIR), "install"])
        _run([pkg, "--dir", str(FRONTEND_DIR), "build"])
    else:
        _run([pkg, "--prefix", str(FRONTEND_DIR), "install"])
        _run([pkg, "--prefix", str(FRONTEND_DIR), "run", "build"])


def build(services: list[str], frontend: bool) -> None:
    check_docker()
    if frontend:
        build_frontend()
    targets = _resolve_services(services)
    _run(["docker", "compose", "-f", COMPOSE_FILE, "build"] + targets)


def up(services: list[str], build_flag: bool) -> None:
    check_env()
    check_docker()
    if build_flag:
        build(services, frontend=True)
    check_frontend_dist()
    targets = _resolve_services(services)
    _run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"] + targets)
    health(wait=120)


def down(services: list[str], volumes: bool) -> None:
    check_docker()
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "down"]
    if volumes:
        cmd.append("--volumes")
    targets = _resolve_services(services)
    cmd += targets
    _run(cmd)


def ps() -> None:
    check_docker()
    _run(["docker", "compose", "-f", COMPOSE_FILE, "ps"])


def logs(services: list[str], follow: bool = False) -> None:
    check_docker()
    targets = _resolve_services(services)
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "logs", "--tail=200"]
    if follow:
        cmd.append("-f")
    _run(cmd + targets)


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status < 500
    except Exception:  # noqa: BLE001
        return False


def health(wait: int = 120) -> None:
    """轮询全部模块健康端点，直至就绪或超时。"""
    deadline = time.time() + wait
    pending = set(HEALTH_URLS)
    while pending and time.time() < deadline:
        for name in list(pending):
            if _http_ok(HEALTH_URLS[name]):
                print(f"[ok] {name} 已就绪")
                pending.discard(name)
        if pending:
            time.sleep(2)
    if pending:
        print("健康检查未通过，未就绪:", ", ".join(sorted(pending)))
        raise SystemExit(1)
    print("全部模块就绪 ✅")


def main() -> int:
    parser = argparse.ArgumentParser(description="精卫一键部署与运维")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="构建前端与镜像")
    p_build.add_argument("--services", default="", help="逗号分隔模块名，如 gateway,query")
    p_build.add_argument("--no-frontend", action="store_true", help="跳过前端构建")

    p_up = sub.add_parser("up", help="启动服务（按需启停）")
    p_up.add_argument("--services", default="", help="逗号分隔模块名，如 gateway,query")
    p_up.add_argument("--no-build", action="store_true", help="跳过构建直接启动")
    p_up.add_argument("--wait", type=int, default=120, help="健康检查等待秒数")

    p_down = sub.add_parser("down", help="停止服务")
    p_down.add_argument("--services", default="", help="逗号分隔模块名")
    p_down.add_argument("--volumes", action="store_true", help="同时删除数据卷")

    sub.add_parser("ps", help="查看容器状态")

    p_health = sub.add_parser("health", help="健康检查")
    p_health.add_argument("--wait", type=int, default=120)

    p_logs = sub.add_parser("logs", help="查看服务日志")
    p_logs.add_argument("--services", default="gateway", help="逗号分隔模块名")
    p_logs.add_argument("-f", "--follow", action="store_true", help="跟踪输出")

    args = parser.parse_args()
    names = [s.strip() for s in args.services.split(",") if s.strip()] if args.services else []

    if args.cmd == "build":
        build(names, frontend=not args.no_frontend)
    elif args.cmd == "up":
        up(names, build_flag=not args.no_build)
    elif args.cmd == "down":
        down(names, volumes=args.volumes)
    elif args.cmd == "ps":
        ps()
    elif args.cmd == "health":
        health(wait=args.wait)
    elif args.cmd == "logs":
        logs(names or ["gateway"], follow=args.follow)
    return 0


if __name__ == "__main__":
    sys.exit(main())
