from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.gpu_insights_snapshot import GpuInsightsSnapshotRow
from app.models.gpu_metric import GpuMetric
from app.models.server_metric import ServerMetric


def fetch_metrics_history(
    db: Session,
    server_id: int,
    *,
    hours: float = 1.0,
    max_host_points: int = 500,
    max_gpu_points: int = 4000,
) -> tuple[list[ServerMetric], list[GpuMetric], list[GpuInsightsSnapshotRow]]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    host = (
        db.query(ServerMetric)
        .filter(ServerMetric.server_id == server_id, ServerMetric.collected_at >= since)
        .order_by(ServerMetric.collected_at.asc())
        .limit(max_host_points)
        .all()
    )
    gpu = (
        db.query(GpuMetric)
        .filter(
            GpuMetric.server_id == server_id,
            GpuMetric.collected_at >= since,
            GpuMetric.status == "ok",
        )
        .order_by(GpuMetric.collected_at.asc(), GpuMetric.gpu_index.asc())
        .limit(max_gpu_points)
        .all()
    )
    insights = (
        db.query(GpuInsightsSnapshotRow)
        .filter(GpuInsightsSnapshotRow.server_id == server_id, GpuInsightsSnapshotRow.collected_at >= since)
        .order_by(GpuInsightsSnapshotRow.collected_at.asc())
        .limit(max_host_points)
        .all()
    )
    return host, gpu, insights
