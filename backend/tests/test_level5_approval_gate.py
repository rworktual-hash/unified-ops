import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.executors.controlled import execute_approved_action
from app.services.approval_flow import approve_request


def _gpu():
    return SimpleNamespace(
        id=1,
        server_name="DR-GPU1-148",
        server_type="gpu",
        project="ai",
        is_active=True,
        ip_address="81.17.61.148",
        ssh_port=4204,
        ssh_username="linuxteam",
        credential_ref="gpu_key_1",
        ssh_password=None,
        ssh_auth_mode="key",
    )


def test_approve_without_confirm_does_not_execute():
    row = SimpleNamespace(status="pending", server_id=1, id=9)
    db = MagicMock()
    db.get.return_value = row
    with patch("app.services.approval_flow.execute_approved_action") as execute:
        with pytest.raises(ValueError, match="Second confirmation"):
            approve_request(db, 9, decided_by="operator", confirmed=False)
        execute.assert_not_called()
    assert row.status == "pending"


def test_confirm_without_pending_approval_is_blocked():
    row = SimpleNamespace(status="rejected", server_id=1, id=9)
    db = MagicMock()
    db.get.return_value = row
    with patch("app.services.approval_flow.execute_approved_action") as execute:
        with pytest.raises(ValueError, match="not pending"):
            approve_request(db, 9, decided_by="operator", confirmed=True)
        execute.assert_not_called()


def test_execute_unknown_unit_does_not_open_ssh():
    db = MagicMock()
    with patch("app.monitoring.ssh_client.ssh_session") as ssh:
        result = execute_approved_action(
            db,
            _gpu(),
            "systemctl_restart",
            json.dumps({"service_name": "sshd"}),
        )
        ssh.assert_not_called()
    assert result.success is False
    assert "sshd" in (result.detail or "")


def test_execute_on_portal_ip_does_not_open_ssh():
    host = _gpu()
    host.ip_address = "10.180.1.222"
    db = MagicMock()
    with patch("app.monitoring.ssh_client.ssh_session") as ssh:
        result = execute_approved_action(
            db,
            host,
            "systemctl_restart",
            json.dumps({"service_name": "docker"}),
        )
        ssh.assert_not_called()
    assert result.success is False
    assert ".222" in (result.detail or "")


def test_successful_restart_uses_exact_command_then_recollects():
    db = MagicMock()
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = b""
    stderr = MagicMock()
    stderr.read.return_value = b""
    client = MagicMock()
    client.exec_command.return_value = (None, stdout, stderr)
    session = MagicMock()
    session.__enter__.return_value = client
    session.__exit__.return_value = False
    metric = SimpleNamespace(id=44)
    with (
        patch("app.monitoring.ssh_client.ssh_session", return_value=session),
        patch("app.executors.controlled.collect_and_store_metrics", return_value=(metric, [])) as collect,
    ):
        result = execute_approved_action(
            db,
            _gpu(),
            "systemctl_restart",
            json.dumps({"service_name": "docker"}),
        )
    client.exec_command.assert_called_once_with("sudo systemctl restart docker", timeout=60)
    collect.assert_called_once()
    assert result.success is True
    assert "host_metric_id=44" in result.message
