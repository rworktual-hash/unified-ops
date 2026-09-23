"""Read-only service flags used to propose a Level 5 restart. Never restarts."""

from app.models.server import Server
from app.policies.executor_actions import is_portal_host, recovery_unit
from app.services.server_ssh import ssh_kwargs_from_server


def tool_check_recovery_signals(server: Server) -> dict:
    """Explicit True/False from existing collectors. Missing flag is not 'down'."""
    if is_portal_host(server) or not server.is_active:
        return {}
    if (server.server_type or "").lower() == "gpu":
        return {}
    if recovery_unit(server) is None:
        return {}
    project = (server.project or "").lower()
    server_type = (server.server_type or "").lower()
    try:
        kw = ssh_kwargs_from_server(server)
        if project == "voicemg":
            from app.monitoring.voicemg_ssh_collectors import collect_voicemg_ssh_insights

            snap = collect_voicemg_ssh_insights(**kw, server_name=server.server_name)
            return {"docker_active": snap.docker_active, "error": snap.error}
        if project == "email":
            from app.monitoring.email_ssh_collectors import collect_email_ssh_insights

            snap = collect_email_ssh_insights(**kw)
            return {"postfix_active": snap.postfix_active, "error": snap.error}
        if project == "backupvault":
            from app.monitoring.backupvault_ssh_collectors import collect_backupvault_ssh_insights

            snap = collect_backupvault_ssh_insights(
                **kw, server_name=server.server_name, server_type=server.server_type
            )
            return {"docker_active": snap.docker_active, "error": snap.error}
        if server_type in {"nginx", "sip", "pbx"}:
            from app.monitoring.infrastructure_ssh_collectors import collect_infrastructure_ssh_insights

            snap = collect_infrastructure_ssh_insights(
                **kw, server_name=server.server_name, server_type=server.server_type
            )
            if server_type == "nginx":
                return {"nginx_active": snap.nginx_active, "error": snap.error}
            return {"docker_active": snap.docker_active, "error": snap.error}
    except Exception as exc:
        return {"error": str(exc)[:300]}
    return {}
