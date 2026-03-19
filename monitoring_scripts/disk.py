from __future__ import annotations

from typing import Any

import psutil


def collect_disk() -> dict[str, Any]:
    """
    Disk usage per mounted partition (cross-platform via psutil).
    """
    partitions: list[dict[str, Any]] = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        partitions.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent": round(
                    (usage.used / usage.total) * 100.0, 4
                )
                if usage.total
                else 0.0,
            }
        )
    return {"partitions": partitions}
