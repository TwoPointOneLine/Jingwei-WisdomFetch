#!/usr/bin/env python
"""
精卫 · 一键启动脚本

职责：
  1. 检查基础设施（Milvus / MongoDB / MinIO）连通性，未就绪则给出引导提示；
  2. 并行拉起 网关(gateway-server) / 认证(auth-server) / 导入(import-server) /
     查询(query-server) / 用户(user-server) 五个 uvicorn；
  3. 等待服务启动完成并通过健康探测；
  4. 输出访问地址（统一入口为网关 8080）。

用法：
  uv run python scripts/start_all.py                # 启动（前台常驻，Ctrl+C 停止）
  uv run python scripts/start_all.py --with-infra   # 先拉起并等待基础设施，再启动服务
  uv run python scripts/start_all.py --stop         # 停止已启动的服务
  uv run python scripts/start_all.py --check        # 仅检查环境，不启动

说明：
  - 端口读取自 .env 的 GATEWAY_APP_PORT / AUTH_APP_PORT / IMPORT_APP_PORT /
    QUERY_APP_PORT / USER_APP_PORT（默认 8080 / 8083 / 8081 / 8082 / 8084）；
  - 服务均来自独立模块：jingwei_gateway / jingwei_auth /
    jingwei_knowledge / jingwei_query / jingwei_user；
  - 默认服务启动后脚本前台常驻并实时回显日志，按 Ctrl+C（或 SIGTERM）统一停止全部服务；
  - 基础设施容器：--with-infra 会自动 `docker compose -f deploy/docker-compose.yml up -d`
    并轮询 healthy；否则请手动：`docker compose -f deploy/docker-compose.yml up -d`。
"""
import argparse
import io
import os
import shlex
import shutil
import signal
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
        "module": "jingwei_gateway.api.gateway_server.main:app",
        "port": GATEWAY_PORT,
    },
    "auth-server": {
        "module": "jingwei_auth.api.auth_server.main:app",
        "port": AUTH_PORT,
    },
    "import-server": {
        "module": "jingwei_knowledge.api.import_server.main:app",
        "port": IMPORT_PORT,
    },
    "query-server": {
        "module": "jingwei_query.api.query_server.main:app",
        "port": QUERY_PORT,
    },
    "user-server": {
        "module": "jingwei_user.api.user_server.main:app",
        "port": USER_PORT,
    },
}

# 基础设施探测地址（Milvus/Mongo/MinIO，按 .env 或默认值）
INFRA_PROBES = [
    ("Milvus", os.getenv("MILVUS_URL", "http://127.0.0.1:19530")),
    ("MongoDB", os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")),
    ("MinIO", os.getenv("MINIO_ENDPOINT", "localhost:9000")),
]

# 基础设施容器编排文件（含 mongo / milvus / object-storage 等）
# deploy/ 在仓库根（backend 的上一级），而非 backend 内
COMPOSE_FILE = PROJECT_ROOT.parent / "deploy" / "docker-compose.yml"



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
    print(" 精卫 · 一键启动")
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
        print('       docker compose -f ../deploy/docker-compose.yml up -d')
        print("       （Milvus/Mongo/MinIO 全部 healthy 后重试）")
        print("       服务可先启动，但涉及向量检索/持久化的功能会降级。")
    else:
        print("      基础设施全部就绪。")
    return all_ok


# --------------------------------------------------------------------------- #
# 基础设施拉起（可选）
# --------------------------------------------------------------------------- #
def start_infra(timeout: float = 300.0) -> bool:
    """用 docker compose 拉起基础设施并轮询 healthy。"""
    if not COMPOSE_FILE.exists():
        print(f"\n[错误] 找不到编排文件：{COMPOSE_FILE}")
        return False
    print("\n[*] 拉起基础设施（docker compose up -d）...")
    r = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
        cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        print("      docker compose 执行失败，请检查 Docker 是否运行。")
        return False

    # 轮询各基础设施 TCP 可达（compose 用 healthcheck，这里只探端口）
    print("[*] 等待基础设施就绪 ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(tcp_probe(addr) for _, addr in INFRA_PROBES):
            print("      基础设施全部就绪。")
            return True
        time.sleep(2.0)
    print("      等待超时，部分基础设施仍不可达（详见 docker compose ps）。")
    return False


# --------------------------------------------------------------------------- #
# 服务启动 / 停止
# --------------------------------------------------------------------------- #
def _uv_python_cmd() -> list:
    """返回用于启动服务子进程的命令前缀。

    优先使用 uv 工作区虚拟环境（依赖齐全、可 import 各业务包），
    否则回退到当前解释器。这样即使用户用系统全局 python 调起本脚本，
    服务子进程也能在正确的虚拟环境中运行。
    """
    uv = shutil.which("uv")
    if uv:
        # uv run 会激活工作区 .venv；--no-sync 避免每次拉依赖（首次仍需 uv sync）
        return [uv, "run", "--no-sync", sys.executable, "-m", "uvicorn"]
    return [sys.executable, "-m", "uvicorn"]


def start_servers():
    print("\n[2/3] 启动服务 ...")
    procs = {}
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    base = _uv_python_cmd()
    for name, cfg in _SERVERS.items():
        if port_in_use(cfg["port"]):
            print(f"      - {name} 端口 {cfg['port']} 已被占用，跳过启动（可能已在运行）")
            continue
        log_path = log_dir / f"{name}.log"
        cmd = base + [
            cfg["module"],
            "--host", APP_HOST,
            "--port", str(cfg["port"]),
            "--log-level", "info",
        ]
        print(f"      - 拉起 {name}  ->  http://{APP_HOST}:{cfg['port']}  (日志: {log_path})")
        print(f"        命令: {' '.join(shlex.quote(c) for c in cmd)}")
        # stdout/stderr 走管道，由 _pump_logs 统一按 UTF-8 读、落盘并回显
        procs[name] = {
            "proc": subprocess.Popen(
                cmd, cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                bufsize=1, encoding="utf-8", errors="replace",
            ),
            "log": log_path,
        }
    return procs


def _pump_logs(procs: dict):
    """实时回显各服务日志到控制台（带前缀），并同步落盘。"""
    import threading

    def _tail(name: str, proc: subprocess.Popen, log_path):
        prefix = f"[{name}] "
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    fh.write(line + "\n")
                    fh.flush()
                    print(prefix + line, flush=True)
        except Exception:
            pass

    threads = []
    for name, info in procs.items():
        t = threading.Thread(
            target=_tail, args=(name, info["proc"], info["log"]), daemon=True
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


def wait_healthy(procs: dict, timeout: float = 30.0) -> bool:
    print("\n[3/3] 等待服务健康 ...")
    deadline = time.time() + timeout
    ok = True
    for name, cfg in _SERVERS.items():
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


def stop_servers(ports=None):
    print("\n停止服务 ...")
    targets = ports if ports else [cfg["port"] for cfg in _SERVERS.values()]
    name_by_port = {cfg["port"]: name for name, cfg in _SERVERS.items()}
    for port in targets:
        if not port_in_use(port):
            print(f"      - {name_by_port.get(port, '?')} 端口 {port} 未占用")
            continue
        if os.name == "nt":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-NetTCPConnection -LocalPort {port} -State Listen).OwningProcess"],
                capture_output=True, text=True,
            )
            pids = {p.strip() for p in out.stdout.splitlines() if p.strip()}
            for pid in pids:
                # /T 杀整棵进程树（含 uv run 拉起的 uvicorn 孙进程）
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True)
            print(f"      - {name_by_port.get(port, '?')} :{port} 已停止 (PID {sorted(pids)})")
        else:
            subprocess.run(
                ["sh", "-c", f"kill $(lsof -t -i:{port}) 2>/dev/null"],
                capture_output=True,
            )
            print(f"      - {name_by_port.get(port, '?')} :{port} 已停止")


def main():
    parser = argparse.ArgumentParser(description="精卫一键启动")
    parser.add_argument("--with-infra", action="store_true",
                        help="先拉起并等待基础设施（docker compose）再启动服务")
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

    if args.with_infra:
        if not start_infra():
            sys.exit(1)

    procs = start_servers()
    ok = wait_healthy(procs)
    if not ok:
        print("\n[警告] 有服务未就绪，请查看上方日志 / logs/*.log")

    print("\n" + "=" * 60)
    print(" 启动完成！访问地址（统一入口为网关）：")
    print(f"     前端入口  : http://{APP_HOST}:{GATEWAY_PORT}/")
    print(f"     网关 API  : http://{APP_HOST}:{GATEWAY_PORT}/gateway/docs")
    print(f"     认证服务  : http://{APP_HOST}:{AUTH_PORT}/docs")
    print(f"     用户服务  : http://{APP_HOST}:{USER_PORT}/docs")
    print(f"     导入服务  : http://{APP_HOST}:{IMPORT_PORT}/docs")
    print(f"     查询服务  : http://{APP_HOST}:{QUERY_PORT}/docs")
    print("=" * 60)
    print("\n按 Ctrl+C 停止全部服务 ...\n")

    # 前台常驻：实时回显日志，Ctrl+C 优雅停止
    try:
        _pump_logs(procs)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n收到停止信号，正在关闭服务 ...")
        # 先尝试优雅终止 uv run 包装进程（Unix 转发 TERM，Windows 发 CTRL_BREAK）
        for info in procs.values():
            proc = info["proc"]
            if proc.poll() is None:
                if os.name == "nt":
                    try:
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    except Exception:
                        pass
                else:
                    proc.terminate()
        time.sleep(2)
        if procs:
            # 兜底：按端口强杀整棵进程树（含 uv 拉起的 uvicorn 孙进程）
            stop_servers(list({cfg["port"] for cfg in _SERVERS.values()}))
        print("已全部停止。")


if __name__ == "__main__":
    main()
