"""Idempotent schema updates for GPU AI insights (safe on every API startup)."""

from sqlalchemy import inspect, text

from app.db.session import Base, engine
from app.models.gpu_insights_snapshot import GpuInsightsSnapshotRow
from app.models.gpu_product_snapshot import GpuProductSnapshotRow


def ensure_gpu_ai_insights_schema() -> None:
    insp = inspect(engine)
    tables = insp.get_table_names()
    if "gpu_metrics" in tables:
        cols = {c["name"] for c in insp.get_columns("gpu_metrics")}
        with engine.begin() as conn:
            if "power_w" not in cols:
                conn.execute(text("ALTER TABLE gpu_metrics ADD COLUMN power_w DOUBLE NULL"))
            if "clock_mhz" not in cols:
                conn.execute(text("ALTER TABLE gpu_metrics ADD COLUMN clock_mhz DOUBLE NULL"))
    Base.metadata.create_all(
        bind=engine,
        tables=[GpuInsightsSnapshotRow.__table__, GpuProductSnapshotRow.__table__],
    )
    insp = inspect(engine)
    if "gpu_insights_snapshots" in insp.get_table_names():
        col_meta = {c["name"]: c for c in insp.get_columns("gpu_insights_snapshots")}
        cols = set(col_meta)
        with engine.begin() as conn:
            for col in ("net_rx_bytes", "net_tx_bytes"):
                if col in col_meta and "bigint" not in str(col_meta[col].get("type", "")).lower():
                    conn.execute(
                        text(f"ALTER TABLE gpu_insights_snapshots MODIFY COLUMN {col} BIGINT NULL")
                    )
            if "listen_port_8011" not in cols:
                conn.execute(text("ALTER TABLE gpu_insights_snapshots ADD COLUMN listen_port_8011 INT NULL"))
            if "localhost_ping_ok" not in cols:
                conn.execute(
                    text("ALTER TABLE gpu_insights_snapshots ADD COLUMN localhost_ping_ok TINYINT(1) NULL")
                )
    if "gpu_product_snapshots" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("gpu_product_snapshots")}
        with engine.begin() as conn:
            if "docker_active" not in cols:
                conn.execute(text("ALTER TABLE gpu_product_snapshots ADD COLUMN docker_active TINYINT(1) NULL"))
            if "docker_container_status" not in cols:
                conn.execute(text("ALTER TABLE gpu_product_snapshots ADD COLUMN docker_container_status TEXT NULL"))
            if "process_sample" not in cols:
                conn.execute(text("ALTER TABLE gpu_product_snapshots ADD COLUMN process_sample TEXT NULL"))
            if "log_tail" not in cols:
                conn.execute(text("ALTER TABLE gpu_product_snapshots ADD COLUMN log_tail TEXT NULL"))
