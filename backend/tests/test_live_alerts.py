from unittest.mock import patch

from app.services.live_alerts import (
    attach_inventory,
    fetch_ai_insights_alerts,
    map_alert_row,
    match_inventory_host,
)


def test_match_inventory_prefers_ip():
    inventory = [
        {"id": 1, "server_name": "DR-GPU1-148", "ip_address": "81.17.61.148", "hostname": "gpu148"},
        {"id": 2, "server_name": "other", "ip_address": "10.0.0.2", "hostname": "DR-GPU1-148"},
    ]
    hit = match_inventory_host("81.17.61.148", "DR-GPU1-148", "gpu148", inventory)
    assert hit is not None
    assert hit["id"] == 1


def test_match_inventory_falls_back_to_hostname():
    inventory = [
        {"id": 9, "server_name": "ccaas-vmg1", "ip_address": "10.180.0.76", "hostname": "ccaas-vmg1"},
    ]
    hit = match_inventory_host(None, "ccaas-vmg1", None, inventory)
    assert hit is not None
    assert hit["id"] == 9
    assert match_inventory_host("1.2.3.4", "missing", None, inventory) is None


def test_map_alert_row_skips_secrets():
    out = map_alert_row(
        {
            "id": 44,
            "title": "High CPU",
            "message": "cpu 92%",
            "severity": "critical",
            "alert_type": "cpu",
            "s_ip_address": "81.17.61.148",
            "s_server_name": "DR-GPU1-148",
            "password": "nope",
        }
    )
    assert out["source_id"] == 44
    assert out["severity"] == "critical"
    assert out["ip_address"] == "81.17.61.148"
    assert "password" not in out


def test_attach_inventory_marks_match():
    alerts = [
        map_alert_row(
            {
                "id": 1,
                "title": "disk",
                "s_ip_address": "81.17.61.148",
                "s_server_name": "DR-GPU1-148",
            }
        ),
        map_alert_row({"id": 2, "title": "unknown", "s_ip_address": "9.9.9.9"}),
    ]
    inventory = [{"id": 5, "server_name": "DR-GPU1-148", "ip_address": "81.17.61.148"}]
    out = attach_inventory(alerts, inventory)
    assert out[0]["matched"] is True
    assert out[0]["inventory_server_id"] == 5
    assert out[1]["matched"] is False


@patch("app.services.live_alerts.get_cached", return_value=None)
@patch("app.services.ai_insights_portal.settings")
def test_fetch_skips_without_url(mock_settings, _cache):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_ai_insights_alerts()
    assert out["ok"] is False
    assert out["alerts"] == []
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")
