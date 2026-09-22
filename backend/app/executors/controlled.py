import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.server import Server
from app.monitoring.ssh_test import test_ssh_connection
from app.policies.executor_actions import is_action_allowed
from app.services.metrics_collect import collect_and_store_metrics
from app.services.server_ssh import ssh_kwargs_from_server


@dataclass
class ExecutionResult:
    success: bool
    message: str
    detail: str | None = None


def _parse_params(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def execute_approved_action(
    db: Session,
    server: Server,
    action_key: str,
    action_params_raw: str | None,
) -> ExecutionResult:
    params = _parse_params(action_params_raw)
    allowed, reason = is_action_allowed(action_key, params, server=server)
    if not allowed:
        return ExecutionResult(success=False, message="Execution blocked by policy.", detail=reason)

    if action_key == "recollect_metrics":
        host, _gpus = collect_and_store_metrics(db, server)
        return ExecutionResult(
            success=True,
            message="Metrics recollected and alerts re-evaluated.",
            detail=f"host_metric_id={host.id}",
        )

    if action_key == "ssh_verify":
        result = test_ssh_connection(**ssh_kwargs_from_server(server))
        return ExecutionResult(
            success=result.success,
            message=result.message,
            detail=f"latency_ms={result.latency_ms}",
        )

    if action_key == "systemctl_restart":
        service = params["service_name"].strip()
        from app.monitoring.ssh_client import ssh_session

        cmd = f"sudo systemctl restart {service}"
        try:
            with ssh_session(**ssh_kwargs_from_server(server)) as client:
                _stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
                code = stdout.channel.recv_exit_status()
                out = stdout.read().decode("utf-8", errors="replace")[:500]
                err = stderr.read().decode("utf-8", errors="replace")[:500]
                if code != 0:
                    return ExecutionResult(
                        success=False,
                        message=f"systemctl restart failed (exit {code})",
                        detail=err or out,
                    )
                return ExecutionResult(success=True, message=f"Restarted {service}", detail=out or "ok")
        except Exception as exc:
            return ExecutionResult(success=False, message="Restart command failed", detail=str(exc))

    return ExecutionResult(success=False, message="Unknown action", detail=action_key)
