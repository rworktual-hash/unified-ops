from types import SimpleNamespace
from unittest.mock import patch

from app.policies.executor_actions import SAFE_ACTION_KEYS, is_action_allowed


def _gpu(**kwargs):
    data = {"server_type": "gpu", "is_active": True}
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_safe_actions_are_recollect_and_ssh_verify():
    assert SAFE_ACTION_KEYS == frozenset({"recollect_metrics", "ssh_verify"})
    assert is_action_allowed("recollect_metrics") == (True, "ok")
    assert is_action_allowed("ssh_verify") == (True, "ok")


def test_unknown_action_rejected():
    ok, reason = is_action_allowed("rm_rf")
    assert ok is False
    assert "not allowlisted" in reason


def test_restart_denied_without_gpu_host():
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "docker"})
    assert ok is False
    assert "GPU" in reason


def test_restart_denied_on_non_gpu():
    ok, reason = is_action_allowed(
        "systemctl_restart", {"service_name": "docker"}, server=_gpu(server_type="email")
    )
    assert ok is False
    assert "GPU" in reason


def test_restart_denied_when_gpu_inactive():
    ok, reason = is_action_allowed(
        "systemctl_restart", {"service_name": "docker"}, server=_gpu(is_active=False)
    )
    assert ok is False
    assert "inactive" in reason


def test_restart_docker_ok_on_active_gpu():
    assert is_action_allowed(
        "systemctl_restart", {"service_name": "docker"}, server=_gpu()
    ) == (True, "ok")


def test_restart_nginx_denied_even_on_gpu():
    ok, reason = is_action_allowed(
        "systemctl_restart", {"service_name": "nginx"}, server=_gpu()
    )
    assert ok is False
    assert "docker" in reason


def test_env_allowlist_cannot_add_sshd():
    with patch(
        "app.policies.executor_actions.allowlisted_restart_services",
        return_value=frozenset({"sshd"}),
    ):
        ok, reason = is_action_allowed(
            "systemctl_restart", {"service_name": "sshd"}, server=_gpu()
        )
        assert ok is False
        assert "sshd" in reason
