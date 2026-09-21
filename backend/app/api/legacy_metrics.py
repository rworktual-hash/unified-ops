from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.legacy_metric_point import LegacyMetricPoint
from app.schemas.legacy_metrics import (
    AiInsightExtrasRead,
    BackupVaultDashboardRead,
    BackupVaultIncrementalRead,
    BackupVaultMonitoringRead,
    BackupVaultNfsRead,
    BackupVaultRepositoriesRead,
    BackupVaultRunHistoryRead,
    BackupVaultTargetsRead,
    InventoryCatalogRead,
    InventoryPortalRead,
    LegacyMetricPointRead,
    VoiceMgExtrasRead,
    VoiceMgHistoryRead,
    LegacyOverviewRead,
    LegacyStatusRead,
    LegacyStreamStatusRead,
    LegacySyncResultRead,
)
from app.services.ai_insights_portal import fetch_ai_insights_extras
from app.services.backupvault_portal import (
    fetch_backupvault_dashboard,
    fetch_backupvault_incremental,
    fetch_backupvault_repositories,
)
from app.services.inventory_portal import fetch_inventory_catalog, fetch_inventory_portal
from app.services.voicemg_portal import fetch_voicemg_extras, fetch_voicemg_history
from app.services.legacy_metrics_sync import (
    compute_legacy_overview,
    discover_legacy_schema,
    fetch_backupvault_monitoring,
    fetch_backupvault_nfs,
    fetch_backupvault_run_history,
    fetch_backupvault_targets,
    legacy_sync_status,
    sync_all_legacy_streams,
)

router = APIRouter(prefix="/legacy-metrics", tags=["legacy-metrics"])

ALLOWED_DOMAINS = {"ai_insights", "backupvault", "voicemg", "infrastructure"}


@router.get("/status", response_model=LegacyStatusRead)
def legacy_status(db: Session = Depends(get_db)) -> LegacyStatusRead:
    data = legacy_sync_status(db)
    return LegacyStatusRead(
        configured=data["configured"],
        connection_ok=data["connection_ok"],
        connection_error=data.get("connection_error"),
        scheduled_sync_enabled=data["scheduled_sync_enabled"],
        streams=[LegacyStreamStatusRead.model_validate(s) for s in data["streams"]],
    )


@router.get("/discovery")
def legacy_discovery(_admin=Depends(require_admin)) -> dict:
    result = discover_legacy_schema()
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("error") or result.get("reason") or "Discovery failed",
        )
    return result


@router.get("/backupvault/runs", response_model=BackupVaultRunHistoryRead)
def backupvault_run_history(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
) -> BackupVaultRunHistoryRead:
    return BackupVaultRunHistoryRead.model_validate(fetch_backupvault_run_history(start, end))


@router.get("/backupvault/dashboard", response_model=BackupVaultDashboardRead)
def backupvault_dashboard() -> BackupVaultDashboardRead:
    return BackupVaultDashboardRead.model_validate(fetch_backupvault_dashboard())


@router.get("/backupvault/incremental", response_model=BackupVaultIncrementalRead)
def backupvault_incremental() -> BackupVaultIncrementalRead:
    return BackupVaultIncrementalRead.model_validate(fetch_backupvault_incremental())


@router.get("/backupvault/repositories", response_model=BackupVaultRepositoriesRead)
def backupvault_repositories() -> BackupVaultRepositoriesRead:
    return BackupVaultRepositoriesRead.model_validate(fetch_backupvault_repositories())


@router.get("/backupvault/targets", response_model=BackupVaultTargetsRead)
def backupvault_targets() -> BackupVaultTargetsRead:
    return BackupVaultTargetsRead.model_validate(fetch_backupvault_targets())


@router.get("/backupvault/nfs", response_model=BackupVaultNfsRead)
def backupvault_nfs() -> BackupVaultNfsRead:
    return BackupVaultNfsRead.model_validate(fetch_backupvault_nfs())


@router.get("/backupvault/monitoring", response_model=BackupVaultMonitoringRead)
def backupvault_monitoring() -> BackupVaultMonitoringRead:
    return BackupVaultMonitoringRead.model_validate(fetch_backupvault_monitoring())


@router.get("/inventory", response_model=InventoryPortalRead)
def inventory_portal() -> InventoryPortalRead:
    return InventoryPortalRead.model_validate(fetch_inventory_portal())


@router.get("/inventory/catalog", response_model=InventoryCatalogRead)
def inventory_catalog() -> InventoryCatalogRead:
    return InventoryCatalogRead.model_validate(fetch_inventory_catalog())


@router.get("/ai-insights/extras", response_model=AiInsightExtrasRead)
def ai_insights_extras() -> AiInsightExtrasRead:
    return AiInsightExtrasRead.model_validate(fetch_ai_insights_extras())


@router.get("/voicemg/extras", response_model=VoiceMgExtrasRead)
def voicemg_extras() -> VoiceMgExtrasRead:
    return VoiceMgExtrasRead.model_validate(fetch_voicemg_extras())


@router.get("/voicemg/history", response_model=VoiceMgHistoryRead)
def voicemg_history(
    range_id: str = Query(default="5m", alias="range"),
    group: str = Query(default="all"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    server_id: int | None = Query(default=None),
) -> VoiceMgHistoryRead:
    return VoiceMgHistoryRead.model_validate(
        fetch_voicemg_history(range_id, group, start, end, server_id)
    )


@router.get("/overview/{domain}", response_model=LegacyOverviewRead)
def legacy_overview(
    domain: str,
    hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
) -> LegacyOverviewRead:
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown domain")
    return LegacyOverviewRead.model_validate(compute_legacy_overview(db, domain=domain, hours=hours))


@router.get("/points", response_model=list[LegacyMetricPointRead])
def list_legacy_points(
    domain: str | None = None,
    server_id: int | None = None,
    hours: int | None = Query(default=24, ge=1, le=24 * 30),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[LegacyMetricPointRead]:
    query = db.query(LegacyMetricPoint).order_by(LegacyMetricPoint.recorded_at.desc())
    if domain:
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown domain")
        query = query.filter(LegacyMetricPoint.domain == domain)
    if server_id is not None:
        query = query.filter(LegacyMetricPoint.server_id == server_id)
    if hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.filter(LegacyMetricPoint.recorded_at >= since)
    rows = query.limit(limit).all()
    return [LegacyMetricPointRead.model_validate(r) for r in rows]


@router.post("/sync", response_model=LegacySyncResultRead)
def sync_all_legacy(_admin=Depends(require_admin), db: Session = Depends(get_db)) -> LegacySyncResultRead:
    result = sync_all_legacy_streams(db)
    return LegacySyncResultRead(ok=result["ok"], results=result["results"])


@router.post("/sync/{domain}", response_model=LegacySyncResultRead)
def sync_legacy_domain(
    domain: str,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> LegacySyncResultRead:
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown domain")
    result = sync_all_legacy_streams(db, domain=domain)
    return LegacySyncResultRead(ok=result["ok"], results=result["results"])
