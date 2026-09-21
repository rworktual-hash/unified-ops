from app.services.level5_propose import pick_action_key, parse_guardrail, SAFE_COMMANDS


def test_collect_failed_proposes_ssh_verify():
    assert pick_action_key("collect_failed", None) == "ssh_verify"
    assert pick_action_key("disk_high", "Private key file not found") == "ssh_verify"


def test_other_alerts_propose_recollect_only():
    assert pick_action_key("disk_high", None) == "recollect_metrics"
    assert pick_action_key("gpu_temp_high", None) == "recollect_metrics"


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
