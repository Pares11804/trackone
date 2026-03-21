from __future__ import annotations

import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from monitoring_scripts import collect_cpu, collect_disk, collect_memory

from trackoneagent.control_url import normalize_control_url

logger = logging.getLogger("trackone.trackoneagent")

_PIDFILE_PATH: Path | None = None


def _remove_pidfile() -> None:
    global _PIDFILE_PATH
    if _PIDFILE_PATH is None:
        return
    try:
        _PIDFILE_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    _PIDFILE_PATH = None


def _write_pidfile(path: Path) -> None:
    global _PIDFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")
    _PIDFILE_PATH = path


def _load_dotenv_simple(path: Path) -> None:
    """Minimal KEY=VALUE loader so we don't depend on python-dotenv."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _load_all_config_files() -> None:
    """Portable bundle: optional TRACKONE_CONFIG path, then ./config.env, then trackoneagent/config.env."""
    explicit = os.environ.get("TRACKONE_CONFIG", "").strip()
    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit))
    paths.append(_REPO_ROOT / "config.env")
    paths.append(Path(__file__).resolve().parent / "config.env")
    for p in paths:
        _load_dotenv_simple(p)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def collect_payload() -> dict[str, Any]:
    return {
        "cpu": collect_cpu(interval=0.1),
        "memory": collect_memory(),
        "disk": collect_disk(),
    }


def run_loop() -> int:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    log_path = os.environ.get("TRACKONE_LOGFILE", "").strip()
    if log_path:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        handlers.append(fh)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )

    _load_all_config_files()

    base = normalize_control_url(os.environ.get("TRACKONE_CONTROL_URL", ""))
    token = os.environ.get("TRACKONE_API_TOKEN", "").strip()
    raw_interval = os.environ.get("TRACKONE_INTERVAL_SECONDS", "30")

    if not base or not token:
        logger.error(
            "Set TRACKONE_CONTROL_URL and TRACKONE_API_TOKEN "
            "(copy trackoneagent/config.example.env to trackoneagent/config.env or bundle root config.env)."
        )
        return 1

    pid_raw = os.environ.get("TRACKONE_PIDFILE", "").strip()
    if pid_raw:
        p = Path(pid_raw)
        if not p.is_absolute():
            p = _REPO_ROOT / p
        _write_pidfile(p)
        logger.info("PID file %s (pid=%s)", p, os.getpid())

    try:
        interval = max(5, float(raw_interval))
    except ValueError:
        interval = 30.0

    url = f"{base}/api/v1/ingest/"
    hostname = socket.gethostname()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    logger.info("TrackOne trackoneagent started host=%s interval=%ss url=%s", hostname, interval, url)

    session = requests.Session()
    while True:
        body = {
            "hostname": hostname,
            "timestamp": _utc_iso(),
            "metrics": collect_payload(),
        }
        try:
            r = session.post(url, json=body, headers=headers, timeout=30)
            if r.status_code == 200:
                logger.info("Ingest ok")
            else:
                logger.warning("Ingest failed status=%s body=%s", r.status_code, r.text[:500])
        except requests.RequestException as e:
            logger.warning("Ingest error: %s", e)
        time.sleep(interval)


def main() -> int:
    try:
        code = run_loop()
        return code if code is not None else 0
    except KeyboardInterrupt:
        logger.info("Stopped.")
    finally:
        _remove_pidfile()
    return 0
