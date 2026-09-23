"""Allowlisted Level 5 actions. One recovery command per project, after human confirm."""

from app.config import settings

SAFE_ACTION_KEYS = frozenset({"recollect_metrics", "ssh_verify"})
MUTATING_ACTION_KEYS = frozenset({"systemctl_restart"})
ALL_ACTION_KEYS = SAFE_ACTION_KEYS | MUTATING_ACTION_KEYS

# Exact units. No other systemd name is ever restarted.
RECOVERY_UNITS = frozenset({"docker", "postfix", "nginx", "kong", "grafana-server"})
EXACT_RESTART_COMMANDS = {
    "docker": "sudo systemctl restart docker",
    "postfix": "sudo systemctl restart postfix",
    "nginx": "sudo systemctl restart nginx",
    "kong": "sudo systemctl restart kong",
    "grafana-server": "sudo systemctl restart grafana-server",
}
PORTAL_DB_IP = "10.180.1.222"


def allowlisted_restart_services() -> frozenset[str]:
    """Env cannot add units. The contract list is the only restart set."""
    raw = getattr(settings, "allowlist_restart_services", "") or ""
    env = frozenset(s.strip() for s in raw.split(",") if s.strip())
    if not env:
        return RECOVERY_UNITS
    return env & RECOVERY_UNITS


def gpu_restart_services() -> list[str]:
    return ["docker"]


def is_portal_host(server) -> bool:
    if server is None:
        return False
    return (getattr(server, "ip_address", None) or "").strip() == PORTAL_DB_IP


def recovery_unit(server) -> str | None:
    """The one unit this active inventory host may restart. None = recollect only."""
    if server is None or not getattr(server, "is_active", False) or is_portal_host(server):
        return None
    project = (getattr(server, "project", None) or "").lower()
    server_type = (getattr(server, "server_type", None) or "").lower()
    if server_type == "gpu":
        return "docker"
    if project == "voicemg":
        return "docker"
    if project == "email":
        return "postfix"
    if project == "backupvault":
        return "docker"
    if server_type == "nginx":
        return "nginx"
    if server_type in {"sip", "pbx"}:
        return "docker"
    if server_type == "kong":
        return "kong"
    if server_type == "monitoring":
        return "grafana-server"
    return None


def is_gpu_host(server) -> bool:
    return recovery_unit(server) == "docker" and (getattr(server, "server_type", None) or "").lower() == "gpu"


def is_action_allowed(action_key: str, action_params: dict | None = None, server=None) -> tuple[bool, str]:
    if is_portal_host(server):
        return False, "Execution on MariaDB .222 is blocked."
    if action_key not in ALL_ACTION_KEYS:
        return False, f"Action '{action_key}' is not allowlisted."
    if action_key in SAFE_ACTION_KEYS:
        if server is not None and not getattr(server, "is_active", True):
            return False, "Server is inactive."
        return True, "ok"
    if action_key != "systemctl_restart":
        return False, f"Action '{action_key}' is not allowlisted."
    if server is None or not getattr(server, "is_active", False):
        return False, "Server is inactive."
    unit = recovery_unit(server)
    service = (action_params or {}).get("service_name", "").strip()
    if not service:
        return False, "service_name is required for systemctl_restart."
    if service not in RECOVERY_UNITS or service not in EXACT_RESTART_COMMANDS:
        return False, f"Service '{service}' is not an allowlisted recovery unit."
    if unit is None or service != unit:
        return False, f"Restart of '{service}' is not allowlisted for this host."
    return True, "ok"
