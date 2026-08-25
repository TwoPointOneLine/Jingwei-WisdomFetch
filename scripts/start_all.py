#!/usr/bin/env python
"""
掌柜智库 · 一键启动脚本

职责：
  1. 检查基础设施（Milvus / MongoDB / MinIO）连通性，未就绪则给出引导提示；
  2. 并行拉起 网关(gateway-server) / 认证(auth-server) / 导入(import-server) /
     查询(query-server) / 用户(user-server) 五个 uvicorn；
  3. 等待服务启动完成并通过健康探测；
  4. 输出访问地址（统一入口为网关 8080）。

用法：
  uv run python scripts/start_all.py            # 启动
  uv run python scripts/start_all.py --stop     # 停止已启动的服务
  uv run python scripts/start_all.py --check    # 仅检查环境，不启动

说明：
  - 端口读取自 .env 的 GATEWAY_APP_PORT / AUTH_APP_PORT / IMPORT_APP_PORT /
    QUERY_APP_PORT / USER_APP_PORT（默认 8080 / 8083 / 8081 / 8082 / 8084）；
  - 服务均来自独立模块：shopkeeper_gateway / shopkeeper_auth /
    shopkeeper_knowledge / shopkeeper_query / shopkeeper_user；
  - 基础设施容器请用：docker compose -f deploy/docker-compose.yml up -d。
"""
import argparse
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------- Windows 控制台中文：强制 UTF-8 输出 ----------
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass
elif os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", write_through=True)

# ---------- 定位项目根 ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# ---------- 读取端口配置（带默认值，缺 .env 也能跑） ----------
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


IMPORT_PORT = _env_int("IMPORT_APP_PORT", 8081)
QUERY_PORT = _env_int("QUERY_APP_PORT", 8082)
AUTH_PORT = _env_int("AUTH_APP_PORT", 8083)
USER_PORT = _env_int("USER_APP_PORT", 8084)
GATEWAY_PORT = _env_int("GATEWAY_APP_PORT", 8080)
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")

# uvicorn 服务进程句柄（均为独立模块，见 services/ 与 packages/common/）
_SERVERS = {
    "gateway-server": {
        "module": "shopkeeper_gateway.api.gateway_server.main:app",
        "port": GATEWAY_PORT,
    },
    "auth-server": {
        "module": "shopkeeper_auth.api.auth_server.main:app",
        "port": AUTH_PORT,
    },
    "import-server": {
        "module": "shopkeeper_knowledge.api.import_server.main:app",
        "port": IMPORT_PORT,
    },
    "query-server": {
        "module": "shopkeeper_query.api.query_server.main:app",
        "port": QUERY_PORT,
    },
    "user-server": {
        "module": "shopkeeper_user.api.user_server.main:app",
        "port": USER_PORT,
    },
}

# 基础设施探测地址（Milvus/Mongo/MinIO，按 .env 或默认值）
INFRA_PROBES = [
    ("Milvus", os.getenv("MILVUS_URL", "http://127.0.0.1:19530")),
    ("MongoDB", os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")),
    ("MinIO", os.getenv("MINIO_ENDPOINT", "localhost:9000")),
]


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _host_port(addr: str) -> tuple[str, int]:
    """从 url / mongodb://user:pw@host:port / host:port 解析出 (host, port)。

    优先用 urlparse 处理含 scheme 的 URL（可正确剥离账号密码），
    再退化到 host:port / host 形式。
    """
    from urllib.parse import urlparse

    if "://" in addr:
        parsed = urlparse(addr)
        host = parsed.hostname
        port = parsed.port
        if host and port:
            return host, port
        # 有 scheme 但无端口（如仅 mongodb://host）
        return host or "", port or 0
    if ":" in addr:
        h, p = addr.rsplit(":", 1)
        try:
            return h, int(p)
        except ValueError:
            return addr, 0
    return addr, 0


def tcp_probe(addr: str, timeout: float = 2.0) -> bool:
    host, port = _host_port(addr)
    if not port:
        return False
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


def port_in_use(port: int) -> bool:
    return tcp_probe(f"127.0.0.1:{port}", timeout=0.5)


# --------------------------------------------------------------------------- #
# 环境检查
# --------------------------------------------------------------------------- #
def check_infra() -> bool:
    print("=" * 60)
    print(" 掌柜智库 · 一键启动")
    print("=" * 60)
    print("\n[1/3] 检查基础设施连通性 ...")
    all_ok = True
    for name, addr in INFRA_PROBES:
        ok = tcp_probe(addr)
        status = "OK" if ok else "FAIL"
        print(f"      - {name:<10} {addr:<40} {status}")
        if not ok:
            all_ok = False
    if not all_ok:
        print("\n[警告] 部分基础设施不可达。若容器未启动，请先执行：")
        print('       docker compose -f deploy/docker-compose.yml up -d')
        print("       （Milvus/Mongo/MinIO 全部 healthy 后重试）")
        print("       服务可先启动，但涉及向量检索/持久化的功能会降级。")
    else:
        print("      基础设施全部就绪。")
    return all_ok


# --------------------------------------------------------------------------- #
# 服务启动 / 停止
# --------------------------------------------------------------------------- #
def start_servers():
    print("\n[2/3] 启动服务 ...")
    procs = {}
    for name, cfg in _SERVERS.items():
        if port_in_use(cfg["port"]):
            print(f"      - {name} 端口 {cfg['port']} 已被占用，跳过启动（可能已在运行）")
            continue
        log_dir = PROJECT_ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        stdout = (log_dir / f"{name}.log").open("a", encoding="utf-8")
        stderr = (log_dir / f"{name}.err").open("a", encoding="utf-8")
        cmd = [
            sys.executable, "-m", "uvicorn",
            cfg["module"],
            "--host", APP_HOST,
            "--port", str(cfg["port"]),
            "--log-level", "info",
        ]
        print(f"      - 拉起 {name}  ->  http://{APP_HOST}:{cfg['port']}")
        procs[name] = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    return procs


def wait_healthy(procs: dict, timeout: float = 30.0) -> bool:
    print("\n[3/3] 等待服务健康 ...")
    deadline = time.time() + timeout
    ok = True
    for name, cfg in _SERVERS.items():
        # 若该服务本就已在运行（未被拉起），直接探测
        ready = False
        while time.time() < deadline:
            if port_in_use(cfg["port"]):
                ready = True
                break
            time.sleep(0.5)
        print(f"      - {name:<14} :{cfg['port']}  {'启动完成' if ready else '启动失败/超时'}")
        if not ready:
            ok = False
    return ok


def stop_servers():
    print("\n停止服务 ...")
    for name, cfg in _SERVERS.items():
        if not port_in_use(cfg["port"]):
            print(f"      - {name} 端口 {cfg['port']} 未占用")
            continue
        if os.name == "nt":
            # Windows: 按端口找 PID 并终止
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-NetTCPConnection -LocalPort {cfg['port']} -State Listen).OwningProcess"],
                capture_output=True, text=True,
            )
            pids = {p.strip() for p in out.stdout.splitlines() if p.strip()}
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            print(f"      - {name} :{cfg['port']} 已停止 (PID {sorted(pids)})")
        else:
            # Unix: 发 SIGTERM 给监听该端口的进程
            subprocess.run(
                ["sh", "-c", f"kill $(lsof -t -i:{cfg['port']}) 2>/dev/null"],
                capture_output=True,
            )
            print(f"      - {name} :{cfg['port']} 已停止")


def main():
    parser = argparse.ArgumentParser(description="掌柜智库一键启动")
    parser.add_argument("--stop", action="store_true", help="停止已启动的服务")
    parser.add_argument("--check", action="store_true", help="仅检查环境，不启动")
    args = parser.parse_args()

    if args.stop:
        stop_servers()
        print("\n服务已停止。")
        return

    check_infra()
    if args.check:
        print("\n环境检查完成（未启动服务）。")
        return

    procs = start_servers()
    ok = wait_healthy(procs)

    print("\n" + "=" * 60)
    print(" 启动完成！访问地址（统一入口为网关）：")
    print(f"     前端入口  : http://{APP_HOST}:{GATEWAY_PORT}/")
    print(f"     网关       : http://{APP_HOST}:{GATEWAY_PORT}/gateway/docs")
    print(f"     认证服务  : http://{APP_HOST}:{AUTH_PORT}/docs")
    print(f"     用户服务  : http://{APP_HOST}:{USER_PORT}/docs")
    print(f"     导入服务  : http://{APP_HOST}:{IMPORT_PORT}/html")
    print(f"     查询服务  : http://{APP_HOST}:{QUERY_PORT}/html")
    print("=" * 60)
    print("\n停止服务：uv run python scripts/start_all.py --stop\n")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
