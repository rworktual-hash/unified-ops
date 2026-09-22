from types import SimpleNamespace

from app.services.level5_propose import pick_action_key, pick_proposal, parse_guardrail, SAFE_COMMANDS


def test_collect_failed_proposes_ssh_verify():
    assert pick_action_key("collect_failed", None) == "ssh_verify"
    assert pick_action_key("disk_high", "Private key file not found") == "ssh_verify"


def test_other_alerts_propose_recollect_only():
    assert pick_action_key("disk_high", None) == "recollect_metrics"
    assert pick_action_key("gpu_temp_high", None) == "recollect_metrics"


def test_gpu_docker_down_proposes_restart_docker():
    gpu = SimpleNamespace(server_type="gpu", is_active=True, server_name="DR-GPU1-148", ip_address="1.1.1.1")
    key, params = pick_proposal("gpu_error", None, server=gpu, extras={"docker_active": False})
    assert key == "systemctl_restart"
    assert params["service_name"] == "docker"


def test_non_gpu_docker_down_stays_recollect():
    mail = SimpleNamespace(server_type="email", is_active=True)
    key, _params = pick_proposal("mem_high", None, server=mail, extras={"docker_active": False})
    assert key == "recollect_metrics"


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
