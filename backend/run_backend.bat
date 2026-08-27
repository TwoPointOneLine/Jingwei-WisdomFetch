@echo off
REM Jingwei backend one-click launcher. Front-run (Ctrl+C to stop).
REM Usage: run_backend.bat [--no-infra]
REM   default: start infra (docker compose up -d) then start 5 services
REM   --no-infra: start services only (infra already ready)
cd /d %~dp0
if "%1"=="--no-infra" (uv run python scripts/start_all.py --no-infra) else (uv run python scripts/start_all.py --with-infra)
if errorlevel 1 pause
