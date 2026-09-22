from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.investigate_graph import run_investigate_graph, tool_trace_json
from app.models.agent_action import AgentAction
from app.models.alert import Alert
from app.models.gpu_metric import GpuMetric
from app.models.server import Server
from app.models.server_metric import ServerMetric
from app.policies.guardrails import PHASE5_ALLOW_EXECUTOR, PHASE5_ALLOW_INVESTIGATION
from app.schemas.agent_action import InvestigationResponse
from app.services.level5_propose import propose_after_investigation


class InvestigationNotAllowed(Exception):
    pass


def _latest_metrics(db: Session, server_id: int) -> dict:
    host = (
        db.query(ServerMetric)
        .filter(ServerMetric.server_id == server_id)
        .order_by(ServerMetric.collected_at.desc())
        .first()
    )
    gpus = (
        db.query(GpuMetric)
        .filter(GpuMetric.server_id == server_id)
        .order_by(GpuMetric.collected_at.desc())
        .limit(8)
        .all()
    )
    return {
        "host": {
            "mem_used_pct": host.mem_used_pct if host else None,
            "disk_root_pct": host.disk_root_pct if host else None,
            "load_1m": host.load_1m if host else None,
            "collect_error": host.collect_error if host else None,
        },
        "gpu_count": len(gpus),
    }


def run_investigation(
    db: Session,
    *,
    server_id: int,
    alert_id: int | None = None,
    alert_type: str | None = None,
    alert_message: str | None = None,
) -> InvestigationResponse:
    if not PHASE5_ALLOW_INVESTIGATION:
        raise InvestigationNotAllowed("Investigation disabled by policy.")
    if PHASE5_ALLOW_EXECUTOR:
        raise InvestigationNotAllowed("Executor is not enabled in Phase 5 (investigation only).")

    server = db.get(Server, server_id)
    if server is None:
        raise ValueError("Server not found")
    if not server.is_active:
        raise ValueError("Server is inactive.")

    if alert_id is not None:
        alert = db.get(Alert, alert_id)
        if alert is None or alert.server_id != server_id:
            raise ValueError("Alert not found for this server")
        alert_type = alert.alert_type
        alert_message = alert.message

    metrics = _latest_metrics(db, server_id)
    final = run_investigate_graph(
        {
            "server": server,
            "alert_type": alert_type,
            "alert_message": alert_message,
            "metrics": metrics,
            "tool_results": {},
            "summary": "",
            "diagnosis": "",
            "recommendation": "",
        }
    )

    now = datetime.now(timezone.utc)
    row = AgentAction(
        server_id=server_id,
        alert_id=alert_id,
        action_type="investigate",
        status="completed",
        summary=final["summary"],
        diagnosis=final["diagnosis"],
        recommendation=final["recommendation"],
        tool_trace=tool_trace_json(final.get("tool_results") or {}),
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    approval_id = None
    proposed_action = None
    try:
        extras = (final.get("tool_results") or {}).get("check_readonly_extras") or {}
        approval = propose_after_investigation(
            db,
            server=server,
            alert_id=alert_id,
            alert_type=alert_type,
            alert_message=alert_message,
            diagnosis=final.get("diagnosis"),
            host_collect_error=(metrics.get("host") or {}).get("collect_error"),
            extras=extras,
        )
        approval_id = approval.id
        proposed_action = approval.action_key
        row.recommendation = f"pending_approval:{approval.action_key}"
        db.commit()
    except ValueError:
        row.recommendation = "monitor_only"
        db.commit()

    return InvestigationResponse(
        agent_action_id=row.id,
        summary=row.summary,
        diagnosis=row.diagnosis,
        recommendation=row.recommendation,
        approval_id=approval_id,
        proposed_action=proposed_action,
    )
