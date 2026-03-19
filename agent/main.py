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

logger = logging.getLogger("trackone.agent")


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


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def collect_payload() -> dict[str, Any]:
    return {
        "cpu": collect_cpu(interval=0.1),
        "memory": collect_memory(),
        "disk": collect_disk(),
    }


def run_loop() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    env_file = Path(__file__).resolve().parent / "config.env"
    _load_dotenv_simple(env_file)

    base = os.environ.get("TRACKONE_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("TRACKONE_API_TOKEN", "").strip()
    raw_interval = os.environ.get("TRACKONE_INTERVAL_SECONDS", "30")

    if not base or not token:
        logger.error(
            "Set TRACKONE_CONTROL_URL and TRACKONE_API_TOKEN "
            "(optional: copy agent/config.example.env to agent/config.env)."
        )
        return 1

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

    logger.info("TrackOne agent started host=%s interval=%ss url=%s", hostname, interval, url)

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
        run_loop()
    except KeyboardInterrupt:
        logger.info("Stopped.")
    return 0
