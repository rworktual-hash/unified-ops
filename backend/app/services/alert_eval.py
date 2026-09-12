from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric


@dataclass
class AlertCandidate:
    alert_type: str
    severity: str
    title: str
    message: str
    active: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_candidates(
    server: Server,
    host: ServerMetric,
    gpu_rows: list[GpuMetric],
) -> list[AlertCandidate]:
    candidates: list[AlertCandidate] = []

    if host.collect_error:
        candidates.append(
            AlertCandidate(
                alert_type="collect_failed",
                severity="critical",
                title="Metric collection failed",
                message=host.collect_error[:1000],
                active=True,
            )
        )
    else:
        candidates.append(
            AlertCandidate(
                alert_type="collect_failed",
                severity="critical",
                title="Metric collection failed",
                message="",
                active=False,
            )
        )

    if host.mem_used_pct is not None:
        over = host.mem_used_pct >= settings.alert_mem_used_pct_warning
        candidates.append(
            AlertCandidate(
                alert_type="mem_high",
                severity="warning",
                title="High memory usage",
                message=f"RAM {host.mem_used_pct:.1f}% (threshold {settings.alert_mem_used_pct_warning}%)",
                active=over,
            )
        )

    if host.disk_root_pct is not None:
        pct = host.disk_root_pct
        if pct >= settings.alert_disk_used_pct_critical:
            sev = "critical"
        elif pct >= settings.alert_disk_used_pct_warning:
            sev = "warning"
        else:
            sev = "warning"
        candidates.append(
            AlertCandidate(
                alert_type="disk_high",
                severity=sev if pct >= settings.alert_disk_used_pct_warning else "warning",
                title="High disk usage on /",
                message=f"Disk {pct:.1f}% (warn {settings.alert_disk_used_pct_warning}%, "
                f"crit {settings.alert_disk_used_pct_critical}%)",
                active=pct >= settings.alert_disk_used_pct_warning,
            )
        )

    for gm in gpu_rows:
        if gm.status != "ok":
            candidates.append(
                AlertCandidate(
                    alert_type=f"gpu_error_{gm.gpu_index}",
                    severity="critical",
                    title=f"GPU {gm.gpu_index} check failed",
                    message=gm.collect_error or f"status={gm.status}",
                    active=True,
                )
            )
            continue
        candidates.append(
            AlertCandidate(
                alert_type=f"gpu_error_{gm.gpu_index}",
                severity="critical",
                title=f"GPU {gm.gpu_index} check failed",
                message="",
                active=False,
            )
        )
        if gm.temperature_c is not None and gm.temperature_c >= settings.alert_gpu_temp_c_warning:
            candidates.append(
                AlertCandidate(
                    alert_type=f"gpu_temp_high_{gm.gpu_index}",
                    severity="warning",
                    title=f"GPU {gm.gpu_index} temperature high",
                    message=f"{gm.temperature_c:.0f}°C (threshold {settings.alert_gpu_temp_c_warning}°C)",
                    active=True,
                )
            )
        else:
            candidates.append(
                AlertCandidate(
                    alert_type=f"gpu_temp_high_{gm.gpu_index}",
                    severity="warning",
                    title=f"GPU {gm.gpu_index} temperature high",
                    message="",
                    active=False,
                )
            )

    if server.server_type == "gpu":
        candidates.append(
            AlertCandidate(
                alert_type="gpu_missing",
                severity="warning",
                title="No GPU metrics returned",
                message="Expected GPU data but collector returned nothing.",
                active=len(gpu_rows) == 0,
            )
        )

    return candidates


def evaluate_alerts(
    db: Session,
    server: Server,
    host: ServerMetric,
    gpu_rows: list[GpuMetric],
) -> None:
    now = _now()
    seen_types = set()
    for cand in _build_candidates(server, host, gpu_rows):
        seen_types.add(cand.alert_type)
        existing = (
            db.query(Alert)
            .filter(
                Alert.server_id == server.id,
                Alert.alert_type == cand.alert_type,
                Alert.status == "open",
            )
            .first()
        )
        if cand.active:
            if existing:
                existing.last_seen_at = now
                existing.message = cand.message
                existing.severity = cand.severity
                existing.title = cand.title
            else:
                db.add(
                    Alert(
                        server_id=server.id,
                        alert_type=cand.alert_type,
                        severity=cand.severity,
                        status="open",
                        title=cand.title,
                        message=cand.message,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
        elif existing:
            existing.status = "resolved"
            existing.resolved_at = now
            existing.last_seen_at = now

    db.commit()
