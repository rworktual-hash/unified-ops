"""Allowlisted executor actions. Mutating restart is GPU hosts only."""

from app.config import settings

# Safe actions (no mutating remote state beyond read/check).
SAFE_ACTION_KEYS = frozenset({"recollect_metrics", "ssh_verify"})

# Mutating actions: GPU + named service only. Never reboot / nvidia-smi -r.
MUTATING_ACTION_KEYS = frozenset({"systemctl_restart"})
GPU_RESTART_SERVICES = frozenset({"docker"})

ALL_ACTION_KEYS = SAFE_ACTION_KEYS | MUTATING_ACTION_KEYS


def allowlisted_restart_services() -> frozenset[str]:
    """Env allowlist is ignored for non-GPU. GPU restart is docker only."""
    raw = getattr(settings, "allowlist_restart_services", "") or ""
    env = frozenset(s.strip() for s in raw.split(",") if s.strip())
    if not env:
        return GPU_RESTART_SERVICES
    return env & GPU_RESTART_SERVICES


def gpu_restart_services() -> list[str]:
    return sorted(GPU_RESTART_SERVICES)


def is_gpu_host(server) -> bool:
    if server is None:
        return False
    return (getattr(server, "server_type", None) or "").lower() == "gpu"


def is_action_allowed(action_key: str, action_params: dict | None = None, server=None) -> tuple[bool, str]:
    if action_key not in ALL_ACTION_KEYS:
        return False, f"Action '{action_key}' is not allowlisted."

    if action_key in SAFE_ACTION_KEYS:
        return True, "ok"

    if action_key == "systemctl_restart":
        if not is_gpu_host(server):
            return False, "Restart is allowed on active GPU hosts only."
        if not getattr(server, "is_active", False):
            return False, "Server is inactive."
        service = (action_params or {}).get("service_name", "").strip()
        if not service:
            return False, "service_name is required for systemctl_restart."
        if service not in GPU_RESTART_SERVICES:
            return False, f"Service '{service}' is not in the GPU restart allowlist (docker only)."
        return True, "ok"

    return False, f"Action '{action_key}' is not allowlisted."
