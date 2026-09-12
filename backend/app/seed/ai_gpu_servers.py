"""AI/GPU inventory from ai_gpu_agent_actions_guide_updated.docx."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.server import Server


@dataclass(frozen=True)
class SeedServer:
    server_name: str
    ip_address: str
    ssh_port: int
    server_type: str
    project: str


AI_GPU_SERVERS: tuple[SeedServer, ...] = (
    SeedServer("AI-GPU-Server-1", "173.234.75.165", 4204, "gpu", "ai"),
    SeedServer("AI-GPU-Server-2", "173.234.75.166", 4204, "gpu", "ai"),
    SeedServer("DR-GPU1-148", "81.17.61.148", 4204, "gpu", "ai"),
    SeedServer("DR-GPU1-149", "81.17.61.149", 4204, "gpu", "ai"),
)


KEY_READY_IPS = frozenset({"81.17.61.148", "81.17.61.149"})


def seed_ai_gpu_servers(db: Session, *, ssh_username: str = "linuxteam") -> tuple[int, int]:
    """Insert AI/GPU servers if IP not already present. Returns (created, skipped)."""
    created = 0
    skipped = 0
    for row in AI_GPU_SERVERS:
        exists = db.query(Server).filter(Server.ip_address == row.ip_address).first()
        if exists:
            skipped += 1
            continue
        db.add(
            Server(
                server_name=row.server_name,
                ip_address=row.ip_address,
                ssh_port=row.ssh_port,
                ssh_username=ssh_username,
                credential_ref="gpu_key_1",
                server_type=row.server_type,
                project=row.project,
                is_active=row.ip_address in KEY_READY_IPS,
            )
        )
        created += 1
    db.commit()
    return created, skipped
