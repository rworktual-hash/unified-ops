"""Combine systemd names with data/process probes for service_active."""


def mysql_service_active(
    *,
    systemd_ok: bool | None,
    db_connections: int | None,
    db_uptime_seconds: int | None,
) -> bool | None:
    if db_connections is not None or db_uptime_seconds is not None:
        return True
    return systemd_ok


def postgres_service_active(
    *,
    systemd_ok: bool | None,
    db_connections: int | None,
) -> bool | None:
    if db_connections is not None:
        return True
    return systemd_ok
