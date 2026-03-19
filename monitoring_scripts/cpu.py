from __future__ import annotations

from typing import Any

import psutil


def collect_cpu(interval: float | None = 0.1) -> dict[str, Any]:
    """
    Return CPU usage snapshot.

    ``interval`` is passed to psutil.cpu_percent (seconds to block for the
    first reading). Use None for non-blocking (may return 0.0 initially).
    """
    percent = psutil.cpu_percent(interval=interval)
    per_cpu = psutil.cpu_percent(interval=None, percpu=True)
    load_avg = None
    try:
        load_avg = [round(x, 4) for x in psutil.getloadavg()]
    except (AttributeError, OSError):
        pass
    return {
        "percent": round(float(percent), 4),
        "per_cpu_percent": [round(float(x), 4) for x in per_cpu] if per_cpu else [],
        "count_logical": psutil.cpu_count(logical=True),
        "count_physical": psutil.cpu_count(logical=False),
        "load_average": load_avg,
    }
