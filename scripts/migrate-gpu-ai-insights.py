#!/usr/bin/env python3
"""Add GPU AI insights columns and gpu_insights_snapshots table (safe to re-run)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.ensure_gpu_ai_insights import ensure_gpu_ai_insights_schema


def main() -> None:
    ensure_gpu_ai_insights_schema()
    print("Migration done (gpu_metrics columns + gpu_insights_snapshots).")


if __name__ == "__main__":
    main()
