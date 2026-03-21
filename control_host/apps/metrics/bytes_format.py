"""Human-readable sizes (1024-based, similar to GNU df -h)."""

from __future__ import annotations


def format_bytes_df_h(n: int | float | None) -> str:
    """Format byte count as e.g. 1.5G, 512M, 20K (matches common df -h style)."""
    if n is None:
        return "—"
    try:
        ni = int(n)
    except (TypeError, ValueError):
        return "—"
    if ni < 0:
        ni = 0
    if ni < 1024:
        return f"{ni}B"
    units = ("K", "M", "G", "T", "P")
    v = float(ni)
    i = 0
    while v >= 1024.0 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    suf = units[i]
    if v >= 100.0 or suf == "K":
        return f"{v:.0f}{suf}"
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{s}{suf}"
