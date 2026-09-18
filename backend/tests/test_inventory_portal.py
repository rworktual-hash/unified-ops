from unittest.mock import MagicMock, patch

from app.services.inventory_portal import (
    _as_gb,
    _build_dashboard,
    _is_online,
    _map_baremetal,
    _safe_columns,
    fetch_inventory_portal,
)


def test_as_gb_bytes_and_already_gb():
    assert _as_gb(None) is None
    assert round(_as_gb(8 * 1024**3) or 0) == 8
    assert _as_gb(256) == 256


def test_is_online():
    assert _is_online("running")
    assert _is_online("Online")
    assert not _is_online("stopped")
    assert not _is_online(None)


def test_map_baremetal_skips_missing_optional():
    row = {
        "id": 3,
        "order_id": "ORD-1",
        "server_id": "HETZ-9",
        "hostname": "px-node-1",
        "host_public_ip": "1.2.3.4",
        "ilo_private_ip": "10.0.0.9",
        "cluster": "px-a",
        "cluster_group": "prod",
        "os": "Debian 12",
        "engineer": "ops",
        "ram": "256GB",
        "cpu": "64",
    }
    mapped = _map_baremetal(row)
    assert mapped["hostname"] == "px-node-1"
    assert mapped["cluster"] == "px-a"
    assert mapped["ram"] == "256GB"
    assert "password" not in mapped


def test_build_dashboard_counts():
    clusters = [
        {
            "id": 1,
            "total_cpu": 100,
            "total_ram_gb": 1000,
            "total_storage_gb": 2000,
            "used_cpu": None,
            "used_ram_gb": None,
            "used_storage_gb": None,
            "cpu_pct": None,
            "ram_pct": None,
            "storage_pct": None,
        }
    ]
    hosts = [
        {
            "cluster_id": 1,
            "status": "online",
            "used_cpu": 20,
            "used_ram_gb": 200,
            "used_storage_gb": 400,
        }
    ]
    vms = [{"status": "running"}, {"status": "stopped"}]
    dash = _build_dashboard(clusters, hosts, [{}, {}], vms, [], [])
    assert dash["baremetal_count"] == 2
    assert dash["host_count"] == 1
    assert dash["total_vms"] == 2
    assert dash["active_vms"] == 1
    assert dash["online_servers"] == 2
    assert dash["total_servers"] == 5
    assert dash["cpu_pct"] == 20.0


def test_safe_columns_drops_secrets():
    conn = MagicMock()
    conn.execute.return_value.all.return_value = [
        ("id",),
        ("hostname",),
        ("ilo_password",),
        ("server_password",),
        ("session_token",),
        ("ssh_password",),
        ("os",),
    ]
    cols = _safe_columns(conn, "baremetal_servers")
    assert cols == ["id", "hostname", "os"]


@patch("app.services.inventory_portal.settings")
def test_fetch_skips_without_url(mock_settings):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_inventory_portal()
    assert out["ok"] is False
    assert out["baremetal"] == []
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")
