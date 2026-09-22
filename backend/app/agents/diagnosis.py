from typing import Any


def build_diagnosis(
    *,
    alert_type: str | None,
    alert_message: str | None,
    metrics: dict[str, Any],
    tool_results: dict[str, Any],
) -> tuple[str, str]:
    """Return (summary, full_diagnosis). Phase 5: text only, no actions."""
    lines: list[str] = []
    if alert_type:
        lines.append(f"Alert type: {alert_type}")
    if alert_message:
        lines.append(f"Alert detail: {alert_message}")

    host = metrics.get("host") or {}
    if host:
        lines.append(
            "Stored metrics: "
            f"RAM {host.get('mem_used_pct')}% · disk {host.get('disk_root_pct')}% · "
            f"load {host.get('load_1m')}"
        )

    host_tool = tool_results.get("check_host_snapshot") or {}
    if host_tool.get("error"):
        lines.append(f"Live host check error: {host_tool['error']}")
    elif host_tool:
        lines.append(
            "Live host check: "
            f"RAM {host_tool.get('mem_used_pct')}% · disk {host_tool.get('disk_root_pct')}% · "
            f"load {host_tool.get('load_1m')}"
        )

    extras = tool_results.get("check_readonly_extras") or {}
    if extras.get("error"):
        lines.append(f"Read-only extras error: {extras['error']}")
    elif extras:
        docker = extras.get("docker_containers_running")
        lines.append(
            "Read-only extras: "
            f"docker {extras.get('docker_active')} · containers {docker}"
        )
        if extras.get("docker_active") is False:
            lines.append("Docker is inactive on this GPU host.")
        if extras.get("process_sample"):
            lines.append(f"Process sample:\n{extras['process_sample']}")
        if extras.get("log_tail"):
            lines.append(f"Log tail:\n{extras['log_tail']}")

    gpu_tool = tool_results.get("check_gpu") or {}
    gpus = gpu_tool.get("gpus") or []
    if gpus:
        for g in gpus:
            lines.append(
                f"GPU {g.get('index')}: util {g.get('utilization_pct')}% · "
                f"temp {g.get('temperature_c')}°C · status {g.get('status')}"
                + (f" · {g.get('error')}" if g.get("error") else "")
            )

    guidance = _guidance_for_alert(alert_type, extras)
    lines.append("")
    lines.append("Assessment (no changes made yet):")
    lines.extend(guidance)
    lines.append("")
    lines.append(
        "Next: the agent will open a pending approval that names the exact command "
        "and impact. Nothing runs until a human Approve + Confirm run. "
        "Reject or Cancel = no command."
    )

    summary = guidance[0] if guidance else "Investigation completed (diagnosis only)."
    return summary, "\n".join(lines)


def _guidance_for_alert(alert_type: str | None, extras: dict[str, Any] | None = None) -> list[str]:
    extras = extras or {}
    if extras.get("docker_active") is False:
        return [
            "Docker is down on this GPU host — the agent will ask to run `sudo systemctl restart docker`.",
            "That command waits for Approve + Confirm run. It does not reboot or reset GPUs.",
        ]
    if not alert_type:
        return ["Review metrics and alerts. Agent will request a read-only recollect after approval."]

    if alert_type == "mem_high":
        return [
            "Memory usage is elevated — review top processes and recent workload changes.",
            "Agent will request a read-only recollect. No restart or process kill.",
        ]
    if alert_type == "disk_high":
        return [
            "Root filesystem usage is high — check logs, caches, and old artifacts.",
            "No destructive deletes from Unified Ops. Agent will request a read-only recollect.",
        ]
    if alert_type.startswith("gpu_temp_high"):
        return [
            "GPU temperature is high — verify cooling/airflow and workload.",
            "No GPU reset or driver changes. Agent will request a read-only recollect.",
        ]
    if alert_type.startswith("gpu_error") or alert_type == "gpu_missing":
        return [
            "GPU check failed or missing — verify nvidia-smi, driver, and hung processes.",
            "If nvidia-smi hangs, treat as incident. No auto GPU reset.",
        ]
    if alert_type == "collect_failed":
        return [
            "Could not collect metrics — verify SSH key, user, port, and network path.",
            "Agent will request SSH verify after approval.",
        ]
    return ["Review alert context and recent metrics. Agent will request a read-only recollect."]
