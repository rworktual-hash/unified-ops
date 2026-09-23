from types import SimpleNamespace

from app.policies.executor_actions import SAFE_ACTION_KEYS, is_action_allowed


def _host(**kwargs):
    data = {
        "server_type": "app",
        "project": "other",
        "is_active": True,
        "ip_address": "10.180.0.10",
        "server_name": "host",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_safe_actions_are_recollect_and_ssh_verify():
    assert SAFE_ACTION_KEYS == frozenset({"recollect_metrics", "ssh_verify"})
    assert is_action_allowed("recollect_metrics") == (True, "ok")
    assert is_action_allowed("ssh_verify") == (True, "ok")


def test_unknown_and_blocked_commands_rejected():
    for key in ("rm_rf", "reboot", "postsuper", "restore", "sftp", "nvidia-smi -r", "kill"):
        ok, reason = is_action_allowed(key, server=_host(server_type="gpu", project="ai"))
        assert ok is False
        assert "not allowlisted" in reason


def test_restart_denied_without_host():
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "docker"})
    assert ok is False
    assert "inactive" in reason


def test_restart_docker_ok_on_gpu_voicemg_backupvault_sip_pbx():
    hosts = [
        _host(server_type="gpu", project="ai"),
        _host(server_type="app", project="voicemg"),
        _host(server_type="app", project="backupvault"),
        _host(server_type="sip", project="infrastructure"),
        _host(server_type="pbx", project="infrastructure"),
    ]
    for host in hosts:
        assert is_action_allowed("systemctl_restart", {"service_name": "docker"}, server=host) == (
            True,
            "ok",
        )


def test_postfix_only_on_email_and_nginx_only_on_nginx():
    email = _host(server_type="app", project="email")
    nginx = _host(server_type="nginx", project="infrastructure")
    assert is_action_allowed("systemctl_restart", {"service_name": "postfix"}, server=email) == (True, "ok")
    assert is_action_allowed("systemctl_restart", {"service_name": "nginx"}, server=nginx) == (True, "ok")
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "docker"}, server=email)
    assert ok is False and "not allowlisted for this host" in reason
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "postfix"}, server=nginx)
    assert ok is False and "not allowlisted for this host" in reason


def test_kong_and_grafana_restart_only_on_their_hosts():
    kong = _host(server_type="kong", project="infrastructure")
    grafana = _host(server_type="monitoring", project="infrastructure")
    database = _host(server_type="database", project="infrastructure")
    assert is_action_allowed("systemctl_restart", {"service_name": "kong"}, server=kong) == (True, "ok")
    assert is_action_allowed("systemctl_restart", {"service_name": "grafana-server"}, server=grafana) == (
        True,
        "ok",
    )
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "grafana-server"}, server=kong)
    assert ok is False and "not allowlisted for this host" in reason
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "kong"}, server=grafana)
    assert ok is False and "not allowlisted for this host" in reason
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "mysql"}, server=database)
    assert ok is False
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "kong"}, server=database)
    assert ok is False and "not allowlisted for this host" in reason


def test_wrong_unit_blocked_on_gpu():
    gpu = _host(server_type="gpu", project="ai")
    for service in ("nginx", "postfix", "kong", "grafana-server", "sshd", "mysql", "mariadb", "postgresql", "voicemg"):
        ok, reason = is_action_allowed("systemctl_restart", {"service_name": service}, server=gpu)
        assert ok is False
        assert service in reason


def test_restart_denied_when_inactive_or_portal():
    gpu = _host(server_type="gpu", project="ai", is_active=False)
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "docker"}, server=gpu)
    assert ok is False and "inactive" in reason
    portal = _host(server_type="gpu", project="ai", ip_address="10.180.1.222")
    ok, reason = is_action_allowed("recollect_metrics", server=portal)
    assert ok is False and ".222" in reason
    ok, reason = is_action_allowed("systemctl_restart", {"service_name": "docker"}, server=portal)
    assert ok is False and ".222" in reason
