from app.monitoring.collectors import collect_gpu_metrics, collect_host_metrics
from app.monitoring.gpu_product_collectors import collect_gpu_product_snapshot
from app.models.server import Server


def tool_check_host_snapshot(server: Server) -> dict:
    snap = collect_host_metrics(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    return {
        "tool": "check_host_snapshot",
        "error": snap.error,
        "load_1m": snap.load_1m,
        "mem_used_pct": snap.mem_used_pct,
        "disk_root_pct": snap.disk_root_pct,
        "uptime_seconds": snap.uptime_seconds,
    }


def tool_check_gpu(server: Server) -> dict:
    rows = collect_gpu_metrics(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    return {
        "tool": "check_gpu",
        "gpus": [
            {
                "index": r.gpu_index,
                "utilization_pct": r.utilization_pct,
                "mem_used_mb": r.mem_used_mb,
                "mem_total_mb": r.mem_total_mb,
                "temperature_c": r.temperature_c,
                "status": r.status,
                "error": r.error,
            }
            for r in rows
        ],
    }


def tool_check_readonly_extras(server: Server) -> dict:
    snap = collect_gpu_product_snapshot(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    return {
        "tool": "check_readonly_extras",
        "error": snap.error,
        "docker_active": snap.docker_active,
        "docker_containers_running": snap.docker_containers_running,
        "docker_container_status": snap.docker_container_status,
        "process_sample": snap.process_sample,
        "log_tail": snap.log_tail,
    }
