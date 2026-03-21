from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone


def _num(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return None


def extract_chart_point(payload: dict[str, Any], collected_at: datetime) -> dict[str, Any]:
    """Map stored JSON payload to numeric series for charts."""
    m = payload.get("metrics")
    if not isinstance(m, dict):
        m = {}

    cpu = m.get("cpu") if isinstance(m.get("cpu"), dict) else {}
    mem = m.get("memory") if isinstance(m.get("memory"), dict) else {}
    virt = mem.get("virtual") if isinstance(mem.get("virtual"), dict) else {}
    disk = m.get("disk") if isinstance(m.get("disk"), dict) else {}
    parts = disk.get("partitions")
    if not isinstance(parts, list):
        parts = []

    disk_pct: float | None = None
    disk_mounts: dict[str, float] = {}
    for p in parts:
        if not isinstance(p, dict):
            continue
        v = _num(p.get("percent"))
        if v is not None:
            disk_pct = v if disk_pct is None else max(disk_pct, v)
        mp = p.get("mountpoint")
        if isinstance(mp, str) and mp and v is not None:
            disk_mounts[mp] = v

    if timezone.is_naive(collected_at):
        collected_at = timezone.make_aware(collected_at, timezone.get_current_timezone())

    return {
        "t": collected_at.isoformat(),
        "cpu": _num(cpu.get("percent")),
        "memory": _num(virt.get("percent")),
        "disk": disk_pct,
        "disk_mounts": disk_mounts,
    }


def downsample(points: list[dict[str, Any]], max_points: int = 2500) -> list[dict[str, Any]]:
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    return points[::step]
