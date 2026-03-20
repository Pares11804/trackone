"""Copy trackoneagent + monitoring_scripts + helper scripts into a portable folder."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def ignore_pyc(_dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]


def build_portable_bundle(out: Path, repo_root: Path) -> None:
    """Populate ``out`` with the same tree as ``scripts/pack_portable_agent.py``."""
    out = out.resolve()
    repo_root = repo_root.resolve()
    out.mkdir(parents=True, exist_ok=True)

    ms_src = repo_root / "monitoring_scripts"
    pkg_src = repo_root / "trackoneagent"
    req_src = repo_root / "trackoneagent" / "requirements.txt"

    if not ms_src.is_dir() or not pkg_src.is_dir():
        print("Repo root must contain monitoring_scripts/ and trackoneagent/.", file=sys.stderr)
        raise FileNotFoundError(ms_src)

    dst_ms = out / "monitoring_scripts"
    dst_pkg = out / "trackoneagent"
    if dst_ms.exists():
        shutil.rmtree(dst_ms)
    if dst_pkg.exists():
        shutil.rmtree(dst_pkg)
    shutil.copytree(ms_src, dst_ms, ignore=ignore_pyc)
    shutil.copytree(pkg_src, dst_pkg, ignore=ignore_pyc)

    shutil.copy2(req_src, out / "requirements.txt")
    ex = pkg_src / "config.example.env"
    if ex.is_file():
        shutil.copy2(ex, out / "config.example.env")
        shutil.copy2(ex, out / "trackoneagent" / "config.example.env")

    (out / "README_PORTABLE.txt").write_text(
        """TrackOne - portable trackoneagent bundle
==========================================

This folder may include a pre-filled config.env if it was built on the control host.

1) Windows: double-click setup_windows.bat (needs Python installed once - creates .venv).
   Linux/macOS: chmod +x *.sh && ./setup_linux.sh

2) If config.env is missing, copy config.example.env to config.env and set URL + token.

3) Run diagnostics: run_agent_check.bat or ./run_agent_check.sh

4) Run trackoneagent:
   Foreground: .venv\\Scripts\\python -m trackoneagent
   Background: start_agent_background.bat or ./start_agent_background.sh

5) Stop: stop_agent.bat or ./stop_agent.sh

For a client with NO Python installed, you need a frozen .exe or a bundle that includes
the Windows embeddable Python - see the main TrackOne README.
""",
        encoding="utf-8",
    )

    (out / "setup_windows.bat").write_text(
        r"""@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 && (set PY=py -3) || (set PY=python)
%PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist config.env (
  if exist config.example.env copy /Y config.example.env config.env
  echo Created config.env from template - edit TRACKONE_CONTROL_URL and TRACKONE_API_TOKEN.
)
echo.
echo Setup done. Run run_agent_check.bat or start_agent_background.bat
pause
""",
        encoding="utf-8",
    )

    (out / "start_agent_background.bat").write_text(
        r"""@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Run setup_windows.bat first.
  exit /b 1
)
set TRACKONE_PIDFILE=%~dp0agent.pid
set TRACKONE_LOGFILE=%~dp0agent.log
start "TrackOneAgent" /MIN /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" -m trackoneagent
echo trackoneagent started in background (minimized window).
echo PID file: %~dp0agent.pid
echo Log file: %~dp0agent.log
timeout /t 2 >nul
""",
        encoding="utf-8",
    )

    (out / "stop_agent.bat").write_text(
        r"""@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist agent.pid (
  echo No agent.pid - nothing to stop.
  exit /b 1
)
set /p PID=<agent.pid
echo Stopping PID !PID!
taskkill /PID !PID! /F 2>nul
del agent.pid 2>nul
echo Done.
""",
        encoding="utf-8",
    )

    (out / "run_agent_check.bat").write_text(
        r"""@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup_windows.bat first.
  exit /b 1
)
.venv\Scripts\python.exe -m trackoneagent.agent_check %*
pause
""",
        encoding="utf-8",
    )

    for name, content in [
        (
            "setup_linux.sh",
            """#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
if [[ ! -f config.env ]] && [[ -f config.example.env ]]; then
  cp config.example.env config.env
  echo "Created config.env - edit TRACKONE_CONTROL_URL and TRACKONE_API_TOKEN"
fi
echo "Setup done."
""",
        ),
        (
            "start_agent_background.sh",
            """#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate
export TRACKONE_PIDFILE="$(pwd)/agent.pid"
export TRACKONE_LOGFILE="$(pwd)/agent.log"
nohup .venv/bin/python -m trackoneagent >> agent.log 2>&1 &
echo $! > agent.pid
echo "Started trackoneagent PID $(cat agent.pid); log: agent.log"
""",
        ),
        (
            "stop_agent.sh",
            """#!/usr/bin/env bash
cd "$(dirname "$0")"
if [[ ! -f agent.pid ]]; then
  echo "No agent.pid"
  exit 1
fi
kill "$(cat agent.pid)" 2>/dev/null || true
rm -f agent.pid
echo "Stopped."
""",
        ),
        (
            "run_agent_check.sh",
            """#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
exec python -m trackoneagent.agent_check "$@"
""",
        ),
    ]:
        p = out / name
        p.write_text(content, encoding="utf-8")
        p.chmod(p.stat().st_mode | 0o111)
