#!/usr/bin/env python3
"""
Build a portable folder you can copy to any Windows/Linux client (TrackOne trackoneagent).

Usage (from repo root):
    python scripts/pack_portable_agent.py
    python scripts/pack_portable_agent.py --out D:\\dist\\trackoneagent
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from packaging.bundle_builder import build_portable_bundle

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "trackoneagent")
    args = ap.parse_args()
    out: Path = args.out.resolve()
    build_portable_bundle(out, ROOT)
    print(f"Portable bundle written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
