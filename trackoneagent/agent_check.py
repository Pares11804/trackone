"""
TrackOne diagnostics: config, collectors, control host reachability, ingest, optional PID check.

Run from the bundle root (folder that contains `trackoneagent/` and `monitoring_scripts/`):

    .venv\\Scripts\\python -m trackoneagent.agent_check

Or:

    python -m trackoneagent.agent_check
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# Bundle root = parent of `trackoneagent/` package
_BUNDLE_ROOT = Path(__file__).resolve().parent.parent
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))


def _load_dotenv_simple(path: Path) -> int:
    n = 0
    if not path.is_file():
        return n
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
            n += 1
    return n


def _config_paths(explicit: Path | None) -> list[Path]:
    if explicit is not None:
        return [explicit]
    return [
        _BUNDLE_ROOT / "config.env",
        _BUNDLE_ROOT / "trackoneagent" / "config.env",
    ]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class StepResult:
    name: str
    ok: bool
    command: str
    detail: str


def _print_step(r: StepResult) -> None:
    mark = "OK " if r.ok else "FAIL"
    print(f"  [{mark}] {r.name}")
    print(f"        command/step: {r.command}")
    if r.detail:
        for line in r.detail.strip().splitlines():
            print(f"        {line}")


def _step_import_collectors() -> StepResult:
    cmd = "import monitoring_scripts (cpu, memory, disk)"
    try:
        from monitoring_scripts import collect_cpu, collect_disk, collect_memory

        collect_cpu(interval=0.05)
        collect_memory()
        collect_disk()
        return StepResult("Local metric collection", True, cmd, "CPU, memory, disk collectors ran without error.")
    except Exception as e:
        return StepResult(
            "Local metric collection",
            False,
            cmd,
            f"Exception: {type(e).__name__}: {e}",
        )


def _step_config(loaded_from: Path | None, keys_from_file: int) -> StepResult:
    base = os.environ.get("TRACKONE_CONTROL_URL", "").strip().rstrip("/")
    token = os.environ.get("TRACKONE_API_TOKEN", "").strip()
    if loaded_from:
        src = f"Loaded {keys_from_file} key(s) from {loaded_from}"
    elif keys_from_file == 0 and (base or token):
        src = "No config file used; TRACKONE_* came from the process environment."
    else:
        src = "No config file found (and no TRACKONE_CONTROL_URL / TOKEN in environment)."
    if not base or not token:
        return StepResult(
            "Configuration",
            False,
            "read TRACKONE_CONTROL_URL + TRACKONE_API_TOKEN",
            f"{src}\nTRACKONE_CONTROL_URL: {'set' if base else 'MISSING'}\nTRACKONE_API_TOKEN: {'set' if token else 'MISSING'}",
        )
    masked = token[:4] + "..." if len(token) > 8 else "(short)"
    return StepResult(
        "Configuration",
        True,
        "read TRACKONE_CONTROL_URL + TRACKONE_API_TOKEN",
        f"{src}\nURL: {base}\nToken (preview): {masked}",
    )


def _step_parse_url(base: str) -> StepResult:
    cmd = f"urlparse({base!r})"
    try:
        p = urlparse(base)
        if p.scheme not in ("http", "https"):
            return StepResult("URL parse", False, cmd, f"Scheme must be http or https, got: {p.scheme!r}")
        if not p.netloc:
            return StepResult("URL parse", False, cmd, "Missing host in URL.")
        return StepResult("URL parse", True, cmd, f"scheme={p.scheme} host={p.hostname} port={p.port or 'default'}")
    except Exception as e:
        return StepResult("URL parse", False, cmd, f"{type(e).__name__}: {e}")


def _step_tcp(base: str) -> StepResult:
    cmd = "socket.create_connection((host, port), timeout=5)"
    try:
        p = urlparse(base)
        host = p.hostname
        port = p.port or (443 if p.scheme == "https" else 80)
        if not host:
            return StepResult("TCP connect to control host", False, cmd, "No hostname in URL.")
        socket.create_connection((host, port), timeout=5).close()
        return StepResult("TCP connect to control host", True, cmd, f"Connected to {host}:{port}")
    except OSError as e:
        return StepResult(
            "TCP connect to control host",
            False,
            cmd,
            f"Could not open TCP connection (firewall, wrong host/port, or service down): {e}",
        )
    except Exception as e:
        return StepResult("TCP connect to control host", False, cmd, f"{type(e).__name__}: {e}")


def _step_http_health(base: str) -> StepResult:
    url = f"{base}/api/v1/health/"
    cmd = f"GET {url}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return StepResult("HTTP health endpoint", True, cmd, f"status={r.status_code} body={r.text[:200]}")
        return StepResult(
            "HTTP health endpoint",
            False,
            cmd,
            f"status={r.status_code} (expected 200) body={r.text[:300]}",
        )
    except requests.RequestException as e:
        return StepResult("HTTP health endpoint", False, cmd, f"requests error: {e}")


def _step_http_ingest(base: str, token: str) -> StepResult:
    url = f"{base}/api/v1/ingest/"
    cmd = f"POST {url} with Bearer token + sample metrics JSON"
    try:
        from monitoring_scripts import collect_cpu, collect_disk, collect_memory

        body = {
            "hostname": socket.gethostname(),
            "timestamp": _utc_iso(),
            "metrics": {
                "cpu": collect_cpu(interval=0.05),
                "memory": collect_memory(),
                "disk": collect_disk(),
            },
        }
        r = requests.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if r.status_code == 200:
            return StepResult("HTTP ingest (auth + payload)", True, cmd, f"status={r.status_code} {r.text[:200]}")
        if r.status_code == 401:
            return StepResult(
                "HTTP ingest (auth + payload)",
                False,
                cmd,
                f"status=401 Unauthorized - wrong TRACKONE_API_TOKEN or host not registered on control server.\n{r.text[:300]}",
            )
        return StepResult(
            "HTTP ingest (auth + payload)",
            False,
            cmd,
            f"status={r.status_code} body={r.text[:400]}",
        )
    except requests.RequestException as e:
        return StepResult("HTTP ingest (auth + payload)", False, cmd, f"requests error: {e}")
    except Exception as e:
        return StepResult("HTTP ingest (auth + payload)", False, cmd, f"{type(e).__name__}: {e}")


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import subprocess

        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return str(pid) in (r.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _step_pidfile(pidfile: Path | None) -> StepResult | None:
    if pidfile is None:
        return None
    cmd = f"read PID from {pidfile} and verify process"
    if not pidfile.is_file():
        return StepResult(
            "trackoneagent process (pidfile)",
            False,
            cmd,
            "Pidfile not found - trackoneagent may not be running in background or TRACKONE_PIDFILE not set when started.",
        )
    try:
        raw = pidfile.read_text(encoding="utf-8").strip()
        pid = int(raw)
    except ValueError:
        return StepResult("trackoneagent process (pidfile)", False, cmd, f"Invalid pidfile contents: {raw!r}")
    alive = _pid_alive(pid)
    if alive:
        return StepResult("trackoneagent process (pidfile)", True, cmd, f"PID {pid} is running.")
    return StepResult(
        "trackoneagent process (pidfile)",
        False,
        cmd,
        f"PID {pid} is not running (stale pidfile or process crashed).",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TrackOne trackoneagent connectivity and health checks.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.env (default: ./config.env then ./trackoneagent/config.env)",
    )
    parser.add_argument(
        "--pidfile",
        type=Path,
        default=None,
        help="If set, verify this pidfile points to a live process (e.g. agent.pid)",
    )
    parser.add_argument(
        "--skip-pidfile",
        action="store_true",
        help="Do not auto-detect agent.pid in bundle root",
    )
    args = parser.parse_args(argv)

    print("TrackOne agent_check (trackoneagent) - running diagnostics\n")

    results: list[StepResult] = []

    loaded_path: Path | None = None
    keys_loaded = 0
    for path in _config_paths(args.config):
        if path.is_file():
            keys_loaded = _load_dotenv_simple(path)
            loaded_path = path
            break

    r_cfg = _step_config(loaded_path, keys_loaded)
    results.append(r_cfg)
    _print_step(r_cfg)

    r_imp = _step_import_collectors()
    results.append(r_imp)
    _print_step(r_imp)

    base = os.environ.get("TRACKONE_CONTROL_URL", "").strip().rstrip("/")
    token = os.environ.get("TRACKONE_API_TOKEN", "").strip()

    if base:
        url_ok = True
        for fn in (_step_parse_url, _step_tcp, _step_http_health):
            r = fn(base)
            results.append(r)
            _print_step(r)
            if not r.ok:
                print("\nStopped further URL checks after failure.\n")
                url_ok = False
                break
        if url_ok:
            if token:
                r = _step_http_ingest(base, token)
                results.append(r)
                _print_step(r)
            else:
                r = StepResult(
                    "HTTP ingest (auth + payload)",
                    False,
                    "POST /api/v1/ingest/",
                    "Skipped - TRACKONE_API_TOKEN not set.",
                )
                results.append(r)
                _print_step(r)
    else:
        print("  (Skipping URL/TCP/HTTP checks - no TRACKONE_CONTROL_URL)\n")

    pidfile = args.pidfile
    if pidfile is None and not args.skip_pidfile:
        for cand in (_BUNDLE_ROOT / "agent.pid", _BUNDLE_ROOT / "trackoneagent" / "agent.pid"):
            if cand.is_file():
                pidfile = cand
                break

    r_pid = _step_pidfile(pidfile)
    if r_pid is not None:
        results.append(r_pid)
        _print_step(r_pid)

    print()
    all_ok = all(r.ok for r in results)
    if all_ok:
        print("Summary: all checks passed.")
        return 0
    failed = [r.name for r in results if not r.ok]
    print(f"Summary: FAILED - {', '.join(failed)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
