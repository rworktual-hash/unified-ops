from unittest.mock import MagicMock, patch

from datetime import date, datetime, timedelta

from app.services.inventory_portal import (
    _as_dt,
    _as_gb,
    _build_dashboard,
    _did_bucket,
    _is_online,
    _map_baremetal,
    _remaining_days,
    _safe_columns,
    _ssl_bucket,
    _team_breakdown,
    fetch_inventory_catalog,
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
    assert dash["teams"][0]["name"] == "Unassigned"
    assert dash["teams"][0]["count"] == 2


def test_team_and_status_buckets():
    teams = _team_breakdown([{"team": "DevOps"}, {"team": "DevOps"}, {"team": "Linux"}])
    assert teams[0]["name"] == "DevOps"
    assert teams[0]["count"] == 2
    assert _did_bucket("Allocated") == "allocated"
    assert _did_bucket("unassigned") == "available"
    assert _did_bucket("reserved") == "reserved"
    assert _ssl_bucket({"status": "active", "remaining_days": 90}) == "active"
    assert _ssl_bucket({"status": "ok", "remaining_days": 12}) == "expiring"
    assert _ssl_bucket({"status": "expired", "remaining_days": -2}) == "expired"


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


@patch("app.services.inventory_portal.get_cached", return_value=None)
@patch("app.services.inventory_portal.settings")
def test_catalog_skips_without_url(mock_settings, _cache):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_inventory_catalog()
    assert out["ok"] is False
    assert out["dids"] == []
    assert out["ssl"] == []
    assert out["domains"] == []
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")


def test_as_dt_promotes_date():
    assert _as_dt(None) is None
    assert _as_dt(date(2026, 1, 15)) == datetime(2026, 1, 15)


def test_remaining_days_uses_valid_to():
    assert _remaining_days(12, None) == 12
    assert _remaining_days(None, date.today() + timedelta(days=7)) == 7
