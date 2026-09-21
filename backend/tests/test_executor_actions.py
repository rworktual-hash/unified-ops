from unittest.mock import patch

from app.policies.executor_actions import SAFE_ACTION_KEYS, is_action_allowed


def test_safe_actions_are_recollect_and_ssh_verify():
    assert SAFE_ACTION_KEYS == frozenset({"recollect_metrics", "ssh_verify"})
    assert is_action_allowed("recollect_metrics") == (True, "ok")
    assert is_action_allowed("ssh_verify") == (True, "ok")


def test_unknown_action_rejected():
    ok, reason = is_action_allowed("rm_rf")
    assert ok is False
    assert "not allowlisted" in reason


def test_restart_hidden_when_allowlist_empty():
    with patch("app.policies.executor_actions.allowlisted_restart_services", return_value=frozenset()):
        ok, reason = is_action_allowed("systemctl_restart", {"service_name": "nginx"})
        assert ok is False
        assert "ALLOWLIST_RESTART_SERVICES" in reason


def test_restart_only_allowlisted_service():
    with patch(
        "app.policies.executor_actions.allowlisted_restart_services",
        return_value=frozenset({"nginx"}),
    ):
        assert is_action_allowed("systemctl_restart", {"service_name": "nginx"}) == (True, "ok")
        ok, reason = is_action_allowed("systemctl_restart", {"service_name": "sshd"})
        assert ok is False
        assert "sshd" in reason
