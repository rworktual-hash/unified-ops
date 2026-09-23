from types import SimpleNamespace

from app.policies.executor_actions import EXACT_RESTART_COMMANDS
from app.services.level5_propose import (
    SAFE_COMMANDS,
    build_guardrail_params,
    parse_guardrail,
    pick_action_key,
    pick_proposal,
)


def _host(**kwargs):
    data = {
        "server_type": "app",
        "project": "other",
        "is_active": True,
        "ip_address": "10.180.0.10",
        "server_name": "host",
        "ssh_port": 22,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_collect_failed_proposes_ssh_verify():
    gpu = _host(server_type="gpu", project="ai")
    assert pick_action_key("collect_failed", None) == "ssh_verify"
    key, params = pick_proposal("disk_high", "Private key file not found", server=gpu, extras={"docker_active": False})
    assert key == "ssh_verify"
    assert params == {}


def test_service_up_or_unknown_proposes_recollect():
    gpu = _host(server_type="gpu", project="ai")
    assert pick_proposal("gpu_temp_high", None, server=gpu, extras={"docker_active": True})[0] == "recollect_metrics"
    assert pick_proposal("gpu_temp_high", None, server=gpu, extras={})[0] == "recollect_metrics"
    assert pick_proposal("gpu_temp_high", None, server=gpu, extras=None)[0] == "recollect_metrics"
    email = _host(project="email")
    assert pick_proposal("mem_high", None, server=email, extras={"postfix_active": True})[0] == "recollect_metrics"


def test_each_project_proposes_only_its_down_unit():
    cases = [
        (_host(server_type="gpu", project="ai"), {"docker_active": False}, "docker"),
        (_host(project="voicemg"), {"docker_active": False}, "docker"),
        (_host(project="backupvault"), {"docker_active": False}, "docker"),
        (_host(server_type="sip", project="infrastructure"), {"docker_active": False}, "docker"),
        (_host(server_type="pbx", project="infrastructure"), {"docker_active": False}, "docker"),
        (_host(project="email"), {"postfix_active": False}, "postfix"),
        (_host(server_type="nginx", project="infrastructure"), {"nginx_active": False}, "nginx"),
    ]
    for host, extras, unit in cases:
        key, params = pick_proposal("service_down", None, server=host, extras=extras)
        assert key == "systemctl_restart"
        assert params["service_name"] == unit
        built = build_guardrail_params(
            server=host,
            action_key=key,
            alert_type="service_down",
            alert_message="unit down",
            diagnosis=None,
            extra_params=params,
        )
        assert built["proposed_command"] == EXACT_RESTART_COMMANDS[unit]


def test_wrong_flag_does_not_propose_another_unit():
    email = _host(project="email")
    assert pick_proposal("mem_high", None, server=email, extras={"docker_active": False})[0] == "recollect_metrics"
    nginx = _host(server_type="nginx", project="infrastructure")
    assert pick_proposal("mem_high", None, server=nginx, extras={"docker_active": False})[0] == "recollect_metrics"
    gpu = _host(server_type="gpu", project="ai")
    assert pick_proposal("mem_high", None, server=gpu, extras={"nginx_active": False})[0] == "recollect_metrics"


def test_inactive_and_portal_do_not_propose_restart():
    inactive = _host(server_type="gpu", project="ai", is_active=False)
    assert pick_proposal("x", None, server=inactive, extras={"docker_active": False})[0] == "recollect_metrics"
    portal = _host(server_type="gpu", project="ai", ip_address="10.180.1.222")
    assert pick_proposal("x", None, server=portal, extras={"docker_active": False})[0] == "recollect_metrics"


def test_unknown_unit_cannot_be_described():
    host = _host(server_type="gpu", project="ai")
    try:
        build_guardrail_params(
            server=host,
            action_key="systemctl_restart",
            alert_type="manual",
            alert_message=None,
            diagnosis=None,
            extra_params={"service_name": "sshd"},
        )
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_safe_catalog_has_no_restart_or_delete():
    assert set(SAFE_COMMANDS) == {"recollect_metrics", "ssh_verify"}


def test_parse_guardrail_reads_reason_and_command():
    raw = (
        '{"alert_type":"disk_high","alert_reason":"disk 87%",'
        '"proposed_command":"SSH collect","impact":"Read-only","host":"DR-GPU1-149"}'
    )
    out = parse_guardrail(raw)
    assert out["alert_type"] == "disk_high"
    assert out["proposed_command"] == "SSH collect"
    assert parse_guardrail("not-json")["alert_reason"] is None
