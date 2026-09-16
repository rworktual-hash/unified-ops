#!/usr/bin/env python3
"""Ensure fleet_collect_runs exists and run_trigger column is correct (nlp-sm one-off)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.ensure_fleet_collect import ensure_fleet_collect_schema  # noqa: E402


def main() -> None:
    ensure_fleet_collect_schema()
    print("fleet_collect_runs schema OK")


if __name__ == "__main__":
    main()
