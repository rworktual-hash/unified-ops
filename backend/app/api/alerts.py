from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.alert import Alert
from app.models.server import Server
from app.schemas.alert import AlertRead, AlertReadWithServer, LiveAlertsRead
from app.schemas.agent_action import InvestigationResponse
from app.services.investigation import InvestigationNotAllowed, run_investigation
from app.services.live_alerts import attach_inventory, fetch_ai_insights_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _inventory_hosts(db: Session) -> list[dict]:
    return [
        {
            "id": row.id,
            "server_name": row.server_name,
            "ip_address": row.ip_address,
            "hostname": row.server_name,
            "is_active": row.is_active,
        }
        for row in db.query(Server).all()
    ]


@router.get("", response_model=list[AlertReadWithServer])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    server_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AlertReadWithServer]:
    q = db.query(Alert, Server).join(Server, Alert.server_id == Server.id)
    if status_filter:
        q = q.filter(Alert.status == status_filter)
    if server_id is not None:
        q = q.filter(Alert.server_id == server_id)
    rows = q.order_by(Alert.last_seen_at.desc()).limit(limit).all()
    result: list[AlertReadWithServer] = []
    for alert, server in rows:
        result.append(
            AlertReadWithServer(
                id=alert.id,
                server_id=alert.server_id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                status=alert.status,
                title=alert.title,
                message=alert.message,
                first_seen_at=alert.first_seen_at,
                last_seen_at=alert.last_seen_at,
                resolved_at=alert.resolved_at,
                server_name=server.server_name,
                ip_address=server.ip_address,
                source="collect",
            )
        )
    return result


@router.get("/live", response_model=LiveAlertsRead)
def list_live_alerts(db: Session = Depends(get_db)) -> LiveAlertsRead:
    payload = fetch_ai_insights_alerts()
    inventory = _inventory_hosts(db)
    alerts = attach_inventory(payload.get("alerts") or [], inventory)
    return LiveAlertsRead(
        ok=bool(payload.get("ok")),
        database=payload.get("database"),
        reason=payload.get("reason"),
        alerts=alerts,
    )


@router.post("/live/{source_id}/investigate", response_model=InvestigationResponse)
def investigate_live_alert(source_id: int, db: Session = Depends(get_db)) -> InvestigationResponse:
    payload = fetch_ai_insights_alerts()
    if not payload.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=payload.get("reason") or "Live alerts unavailable",
        )
    matched = attach_inventory(payload.get("alerts") or [], _inventory_hosts(db))
    alert = next((row for row in matched if row.get("source_id") == source_id), None)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live alert not found")
    server_id = alert.get("inventory_server_id")
    if not server_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No inventory host matches this .222 alert (IP then hostname).",
        )
    if not alert.get("inventory_active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Matched host is inactive (165/166 paused until SSH works). Investigate stays off.",
        )
    try:
        return run_investigation(
            db,
            server_id=int(server_id),
            alert_type=alert.get("alert_type"),
            alert_message=f"[.222] {alert.get('title')}: {alert.get('message')}",
        )
    except InvestigationNotAllowed as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{alert_id}/investigate", response_model=InvestigationResponse)
def investigate_alert(alert_id: int, db: Session = Depends(get_db)) -> InvestigationResponse:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    try:
        return run_investigation(db, server_id=alert.server_id, alert_id=alert_id)
    except InvestigationNotAllowed as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status == "resolved":
        return alert
    now = datetime.now(timezone.utc)
    alert.status = "resolved"
    alert.resolved_at = now
    alert.last_seen_at = now
    db.commit()
    db.refresh(alert)
    return alert
