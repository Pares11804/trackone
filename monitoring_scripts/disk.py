from __future__ import annotations

from typing import Any

import psutil


def _format_bytes_df_h(n: int) -> str:
    """1024-based sizes similar to GNU ``df -h`` (e.g. 1.5G, 512M)."""
    if n < 0:
        n = 0
    if n < 1024:
        return f"{n}B"
    units = ("K", "M", "G", "T", "P")
    v = float(n)
    i = 0
    while v >= 1024.0 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    suf = units[i]
    if v >= 100.0 or suf == "K":
        return f"{v:.0f}{suf}"
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{s}{suf}"


def collect_disk() -> dict[str, Any]:
    """
    Disk usage per mounted partition (cross-platform via psutil).

    Includes machine-readable byte counts and ``df -h``-style strings
    (``size_h``, ``used_h``, ``avail_h``, ``use_pcent``) for each mount.
    Uses ``all=True`` so behavior is closer to ``df -h`` (tmpfs, bind mounts, etc.);
    entries that raise PermissionError/OSError are skipped.
    """
    partitions: list[dict[str, Any]] = []
    for part in psutil.disk_partitions(all=True):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        pct = (
            round((usage.used / usage.total) * 100.0, 2)
            if usage.total
            else 0.0
        )
        partitions.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent": pct,
                "size_h": _format_bytes_df_h(int(usage.total)),
                "used_h": _format_bytes_df_h(int(usage.used)),
                "avail_h": _format_bytes_df_h(int(usage.free)),
                "use_pcent": f"{pct:.0f}%",
            }
        )
    return {"partitions": partitions}
