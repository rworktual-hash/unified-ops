"""Full server inventory from Unified Ops KT and domain guides (IPs/ports as documented)."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.server import Server

DEFAULT_CREDENTIAL_REF = "gpu_key_1"


@dataclass(frozen=True)
class InventoryServer:
    server_name: str
    ip_address: str
    ssh_port: int
    ssh_username: str
    server_type: str
    project: str
    is_active: bool = True
    ssh_auth_mode: str = "auto"
    credential_ref: str | None = DEFAULT_CREDENTIAL_REF


# GPU — non-root users; 165/166 inactive until ssh_password set on server
GPU_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("AI-GPU-Server-1", "173.234.75.165", 4204, "krishna", "gpu", "ai", False, "auto"),
    InventoryServer("AI-GPU-Server-2", "173.234.75.166", 4204, "krishna", "gpu", "ai", False, "auto"),
    InventoryServer("DR-GPU1-148", "81.17.61.148", 4204, "linuxteam", "gpu", "ai", True, "key"),
    InventoryServer("DR-GPU1-149", "81.17.61.149", 4204, "linuxteam", "gpu", "ai", True, "key"),
)

VOICEMG_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("ccaas-vmg1", "10.180.0.76", 22, "root", "app", "voicemg"),
    InventoryServer("ccaas-vmg2", "10.180.0.77", 22, "root", "app", "voicemg"),
    InventoryServer("ccaas-stt1", "10.180.0.93", 4204, "root", "app", "voicemg"),
    InventoryServer("ccaas-stt2", "10.180.0.95", 4204, "root", "app", "voicemg"),
    InventoryServer("ai-vmg1", "10.180.0.83", 4204, "root", "app", "voicemg"),
    InventoryServer("ai-vmg2", "10.180.0.87", 22, "root", "app", "voicemg"),
    InventoryServer("ai-stt1", "10.180.0.97", 4204, "root", "app", "voicemg"),
    InventoryServer("ai-stt2", "10.180.0.98", 4204, "root", "app", "voicemg"),
    InventoryServer("QA-NewAIVMG", "10.180.1.230", 4204, "root", "app", "voicemg"),
)

# Public infra on 82.113.92.* and server-management use SSH port 4204 (not 22).
INFRA_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("server-management", "82.113.72.52", 4204, "root", "infra", "infrastructure"),
    InventoryServer("DevOps-Nginx-1", "82.113.92.115", 4204, "root", "nginx", "infrastructure"),
    InventoryServer("DevOps-Nginx-2", "82.113.92.118", 4204, "root", "nginx", "infrastructure"),
    InventoryServer("DevOps-Nginx-3", "82.113.92.117", 4204, "root", "nginx", "infrastructure"),
    InventoryServer("DevOps-Nginx-4", "82.113.92.116", 4204, "root", "nginx", "infrastructure"),
    InventoryServer("DevOps-Nginx-5", "82.113.92.119", 4204, "root", "nginx", "infrastructure"),
    InventoryServer("AI-KongAPIGW", "82.113.92.106", 4204, "root", "kong", "infrastructure"),
    InventoryServer("CCaaS-Kong-APIGW", "82.113.92.111", 4204, "root", "kong", "infrastructure"),
    InventoryServer("ur-db", "10.180.0.201", 22, "root", "database", "infrastructure"),
    InventoryServer("ai-ccaas-db", "10.180.0.202", 22, "root", "database", "infrastructure"),
    InventoryServer("campaign-db", "10.180.0.203", 22, "root", "database", "infrastructure"),
    InventoryServer("Grafana-Dashboard", "82.113.72.19", 22, "root", "monitoring", "infrastructure"),
    InventoryServer("Apache-Kafka", "82.113.92.124", 4204, "root", "nginx", "infrastructure", True, "key"),
    InventoryServer("CRM-DB", "10.180.0.204", 22, "root", "database", "infrastructure", True, "key"),
    InventoryServer("Ontology-Postgresql", "10.180.0.126", 22, "root", "database", "infrastructure", True, "key"),
)

# AI Insights parity — Redis / PBX / SIP (root + key; ports from aiservers.worktual.tech)
REDIS_SERVERS: tuple[InventoryServer, ...] = tuple(
    InventoryServer(
        f"Redis-{n}",
        f"10.180.0.{octet}",
        22,
        "root",
        "redis",
        "infrastructure",
        True,
        "key",
    )
    for n, octet in enumerate([101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 115], start=1)
)

PBX_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("AI-CCaaS-PBX-1", "10.180.0.56", 22, "root", "pbx", "infrastructure", True, "key"),
    InventoryServer("AI-CCaaS-PBX-2", "10.180.0.96", 22, "root", "pbx", "infrastructure", True, "key"),
    InventoryServer("CCaaS-PBX-1", "10.180.0.68", 22, "root", "pbx", "infrastructure", True, "key"),
    InventoryServer("CCaaS-PBX-2", "10.180.0.71", 22, "root", "pbx", "infrastructure", True, "key"),
)

SIP_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("AI-CCaaS-SGW-1", "10.180.0.57", 4204, "root", "sip", "infrastructure", True, "key"),
    InventoryServer("AI-CCaaS-SGW-2", "10.180.0.64", 22, "root", "sip", "infrastructure", True, "key"),
    InventoryServer("CCaaS-SGW-1", "10.180.0.81", 22, "root", "sip", "infrastructure", True, "key"),
    InventoryServer("CCaaS-SGW-2", "10.180.0.82", 22, "root", "sip", "infrastructure", True, "key"),
)

EMAIL_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("email-mgmt-1", "82.113.72.84", 4204, "root", "app", "email"),
    InventoryServer("email-mgmt-2", "82.113.72.80", 4204, "root", "app", "email"),
    InventoryServer("email-mgmt-private", "10.180.0.84", 4204, "root", "app", "email"),
)

# backupvault/mysql: SSH port varies by host (22 vs 4204); verify from nlp-sm before changing.
BACKUPVAULT_SERVERS: tuple[InventoryServer, ...] = (
    InventoryServer("mysql-slave-119", "10.180.0.119", 22, "root", "database", "backupvault"),
    InventoryServer("mysql-slave-211", "10.180.0.211", 22, "root", "database", "backupvault"),
    InventoryServer("MySQL-Slave-01", "10.180.0.212", 22, "root", "database", "backupvault"),
    InventoryServer("MySQL-Slave-02", "10.180.0.213", 22, "root", "database", "backupvault"),
    InventoryServer("PostgreSQL-Slave-01", "10.180.0.215", 22, "root", "database", "backupvault"),
    InventoryServer("backupvault-90", "10.180.0.90", 22, "root", "app", "backupvault"),
    InventoryServer("backupvault-130", "10.180.0.130", 22, "root", "app", "backupvault"),
    InventoryServer("backupvault-150", "10.180.0.150", 4204, "root", "app", "backupvault"),
    InventoryServer("backupvault-250", "10.180.0.250", 22, "root", "app", "backupvault"),
    InventoryServer("backupvault-85", "10.180.0.85", 22, "root", "app", "backupvault"),
    InventoryServer("backupvault-124", "10.180.0.124", 22, "root", "app", "backupvault"),
)

ALL_INVENTORY: tuple[InventoryServer, ...] = (
    GPU_SERVERS
    + VOICEMG_SERVERS
    + INFRA_SERVERS
    + REDIS_SERVERS
    + PBX_SERVERS
    + SIP_SERVERS
    + EMAIL_SERVERS
    + BACKUPVAULT_SERVERS
)


def upsert_inventory(db: Session, *, update_existing: bool = True) -> tuple[int, int, int]:
    """Insert by IP if missing; optionally refresh metadata on existing rows. Returns created, updated, skipped."""
    created = 0
    updated = 0
    skipped = 0
    for row in ALL_INVENTORY:
        existing = db.query(Server).filter(Server.ip_address == row.ip_address).first()
        if existing is None:
            db.add(
                Server(
                    server_name=row.server_name,
                    ip_address=row.ip_address,
                    ssh_port=row.ssh_port,
                    ssh_username=row.ssh_username,
                    credential_ref=row.credential_ref,
                    ssh_auth_mode=row.ssh_auth_mode,
                    server_type=row.server_type,
                    project=row.project,
                    is_active=row.is_active,
                )
            )
            created += 1
            continue
        if not update_existing:
            skipped += 1
            continue
        existing.server_name = row.server_name
        existing.ssh_port = row.ssh_port
        existing.ssh_username = row.ssh_username
        existing.credential_ref = row.credential_ref
        existing.ssh_auth_mode = row.ssh_auth_mode
        existing.server_type = row.server_type
        existing.project = row.project
        if row.ip_address in {"173.234.75.165", "173.234.75.166"}:
            if not existing.ssh_password:
                existing.is_active = False
        else:
            existing.is_active = row.is_active
        updated += 1
    db.commit()
    return created, updated, skipped
