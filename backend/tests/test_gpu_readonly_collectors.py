from app.monitoring.ai_gpu_insights_collectors import _ALLOWED as INSIGHT_CMDS
from app.monitoring.gpu_product_collectors import (
    _ALLOWED as PRODUCT_CMDS,
    _docker_active,
    sanitize_log_tail,
)


def test_product_commands_are_read_only():
    banned = ("restart", "kill", "rm -", "reboot", "shutdown", "systemctl stop", "systemctl start")
    blob = " ".join(PRODUCT_CMDS).lower()
    for word in banned:
        assert word not in blob


def test_insight_commands_are_read_only():
    banned = ("restart", "kill ", "rm -", "reboot", "shutdown")
    blob = " ".join(INSIGHT_CMDS).lower()
    for word in banned:
        assert word not in blob


def test_sanitize_log_tail_redacts_secrets():
    raw = "ok line\npassword=super-secret\ntoken: abc\nsafe"
    out = sanitize_log_tail(raw)
    assert out is not None
    assert "super-secret" not in out
    assert "abc" not in out
    assert "[redacted]" in out
    assert "ok line" in out


def test_docker_active_parse():
    assert _docker_active("active") is True
    assert _docker_active("inactive") is False
    assert _docker_active("") is None
