"""Allowlisted executor actions for Phase 6."""

from app.config import settings

# Safe actions (no mutating remote state beyond read/check).
SAFE_ACTION_KEYS = frozenset({"recollect_metrics", "ssh_verify"})

# Mutating actions require service name on allowlist.
MUTATING_ACTION_KEYS = frozenset({"systemctl_restart"})

ALL_ACTION_KEYS = SAFE_ACTION_KEYS | MUTATING_ACTION_KEYS


def allowlisted_restart_services() -> frozenset[str]:
    raw = getattr(settings, "allowlist_restart_services", "") or ""
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def is_action_allowed(action_key: str, action_params: dict | None = None) -> tuple[bool, str]:
    if action_key not in ALL_ACTION_KEYS:
        return False, f"Action '{action_key}' is not allowlisted."

    if action_key == "systemctl_restart":
        service = (action_params or {}).get("service_name", "").strip()
        if not service:
            return False, "service_name is required for systemctl_restart."
        allowed = allowlisted_restart_services()
        if not allowed:
            return False, "No restart services configured (ALLOWLIST_RESTART_SERVICES)."
        if service not in allowed:
            return False, f"Service '{service}' is not in ALLOWLIST_RESTART_SERVICES."
    return True, "ok"
