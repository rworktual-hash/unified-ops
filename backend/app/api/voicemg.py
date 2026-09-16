from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.server import Server
from app.models.voicemg_ssh_snapshot import VoiceMgSshSnapshot
from app.schemas.voicemg import (
    VoiceMgOverviewRead,
    VoiceMgServerOverview,
    VoiceMgSnapshotRead,
)

router = APIRouter(prefix="/voicemg", tags=["voicemg"])


@router.get("/ssh-overview", response_model=VoiceMgOverviewRead)
def voicemg_ssh_overview(db: Session = Depends(get_db)) -> VoiceMgOverviewRead:
    servers = (
        db.query(Server)
        .filter(Server.is_active.is_(True), Server.project == "voicemg")
        .order_by(Server.server_name)
        .all()
    )
    items: list[VoiceMgServerOverview] = []
    service_down = 0
    storage_warning = 0
    vmg_hosts = 0
    stt_hosts = 0

    for server in servers:
        row = (
            db.query(VoiceMgSshSnapshot)
            .filter(VoiceMgSshSnapshot.server_id == server.id)
            .order_by(VoiceMgSshSnapshot.collected_at.desc())
            .first()
        )
        if row:
            if row.role == "stt":
                stt_hosts += 1
            else:
                vmg_hosts += 1
            if row.service_active is False:
                service_down += 1
            if row.data_disk_used_pct is not None and row.data_disk_used_pct >= 85:
                storage_warning += 1
        else:
            name = server.server_name.lower()
            if "stt" in name:
                stt_hosts += 1
            else:
                vmg_hosts += 1

        items.append(
            VoiceMgServerOverview(
                server_id=server.id,
                server_name=server.server_name,
                ip_address=server.ip_address,
                server_type=server.server_type,
                snapshot=VoiceMgSnapshotRead.model_validate(row) if row else None,
            )
        )

    return VoiceMgOverviewRead(
        servers=items,
        total_hosts=len(servers),
        collected_hosts=sum(1 for item in items if item.snapshot is not None),
        vmg_hosts=vmg_hosts,
        stt_hosts=stt_hosts,
        service_down=service_down,
        storage_warning=storage_warning,
        note=(
            "Read-only SSH for VoiceMG VMG and STT hosts: Docker, optional systemd units, "
            "app process sample, and nvidia-smi on STT. Configure VOICEMG_*_SERVICE_UNITS and "
            "VOICEMG_LOCAL_HEALTH_URLS for your real service names."
        ),
    )
