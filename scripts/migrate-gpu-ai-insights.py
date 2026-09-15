#!/usr/bin/env python3
"""Add GPU AI insights columns and gpu_insights_snapshots table (safe to re-run)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import inspect, text

from app.db.session import Base, engine
from app.models import gpu_insights_snapshot as _gis  # noqa: F401


def main() -> None:
    insp = inspect(engine)
    if "gpu_metrics" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("gpu_metrics")}
        with engine.begin() as conn:
            if "power_w" not in cols:
                conn.execute(text("ALTER TABLE gpu_metrics ADD COLUMN power_w DOUBLE NULL"))
                print("Added gpu_metrics.power_w")
            if "clock_mhz" not in cols:
                conn.execute(text("ALTER TABLE gpu_metrics ADD COLUMN clock_mhz DOUBLE NULL"))
                print("Added gpu_metrics.clock_mhz")
    else:
        print("gpu_metrics missing — start API once first")

    Base.metadata.create_all(bind=engine, tables=[_gis.GpuInsightsSnapshotRow.__table__])
    print("Ensured gpu_insights_snapshots table exists.")
    print("Migration done.")


if __name__ == "__main__":
    main()
