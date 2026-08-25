@echo off
REM 掌柜智库 · 后端一键启动（双击运行）
REM   自动拉起基础设施(docker compose) + 五大后端服务，前台常驻，Ctrl+C 停止。
REM   如需仅启动服务（基础设施已就绪）：run_backend.bat --no-infra
REM   依赖：uv（https://docs.astral.sh/uv/）、Docker（基础设施容器）。
cd /d %~dp0
if "%1"=="--no-infra" (
    uv run python scripts/start_all.py
) else (
    uv run python scripts/start_all.py --with-infra
)
if errorlevel 1 pause
