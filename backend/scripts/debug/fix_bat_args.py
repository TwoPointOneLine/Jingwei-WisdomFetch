# -*- coding: utf-8 -*-
"""将 run_backend.bat 改为透传所有参数，便于调试(如 run_backend.bat --check)。"""
p = r"run_backend.bat"
content = [
    "@echo off",
    "REM Jingwei backend one-click launcher. Front-run (Ctrl+C to stop).",
    "REM Usage: run_backend.bat [--with-infra|--no-infra|--check|--stop]",
    "REM   default: --with-infra (start infra then services)",
    "cd /d %~dp0",
    'if "%1"=="" (uv run python scripts/start_all.py --with-infra) else (uv run python scripts/start_all.py %*)',
    "if errorlevel 1 pause",
    "",
]
with open(p, "w", encoding="ascii", newline="\r\n") as f:
    f.write("\r\n".join(content))
print("ok")
