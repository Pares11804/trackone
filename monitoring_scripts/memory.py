from __future__ import annotations

from typing import Any

import psutil


def collect_memory() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "virtual": {
            "total_bytes": vm.total,
            "available_bytes": vm.available,
            "used_bytes": vm.used,
            "percent": round(float(vm.percent), 4),
        },
        "swap": {
            "total_bytes": swap.total,
            "used_bytes": swap.used,
            "free_bytes": swap.free,
            "percent": round(float(swap.percent), 4) if swap.total else 0.0,
        },
    }
