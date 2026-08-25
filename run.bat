@echo off
REM 掌柜智库 · 一键启动/停止脚本（合并原 start.bat / stop.bat）
REM   用法：
REM     run.bat                启动全部后端服务（先检查基础设施，前台常驻，Ctrl+C 停止）
REM     run.bat --with-infra   先拉起并等待基础设施(docker compose)再启动服务
REM     run.bat --stop         停止已启动的服务
REM     run.bat --check        仅检查环境，不启动
REM   依赖：uv（https://docs.astral.sh/uv/），会在项目根下运行 scripts/start_all.py
cd /d %~dp0
uv run python scripts/start_all.py %*
if errorlevel 1 pause
