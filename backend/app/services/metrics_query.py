from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gpu_metric import GpuMetric


def latest_gpu_metrics_batch(db: Session, server_id: int, *, max_gpus: int = 32) -> list[GpuMetric]:
    latest_at = (
        db.query(func.max(GpuMetric.collected_at))
        .filter(GpuMetric.server_id == server_id, GpuMetric.status == "ok")
        .scalar()
    )
    if latest_at is None:
        return []
    return (
        db.query(GpuMetric)
        .filter(
            GpuMetric.server_id == server_id,
            GpuMetric.collected_at == latest_at,
            GpuMetric.status == "ok",
        )
        .order_by(GpuMetric.gpu_index.asc())
        .limit(max_gpus)
        .all()
    )
