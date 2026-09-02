@echo off
chcp 65001 >nul
REM Jingwei WisdomFetch - one-shot start/stop helper (merged start.bat / stop.bat)
REM Usage:
REM   run.bat                 start all backend services (check infra, foreground, Ctrl+C to stop)
REM   run.bat --with-infra    bring up and wait for infra (docker compose) before services
REM   run.bat --stop          stop the started services
REM   run.bat --check         check environment only, do not start
REM Deps: uv (https://docs.astral.sh/uv/); runs scripts/start_all.py from project root
cd /d %~dp0
uv run python scripts/start_all.py %*
if errorlevel 1 pause
