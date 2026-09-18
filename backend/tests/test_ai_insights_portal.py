from unittest.mock import patch

from app.services.ai_insights_portal import fetch_ai_insights_extras, flatten_service_payload


def test_flatten_payload_priority_and_secrets():
    tiles = flatten_service_payload(
        {
            "qps": 274.7,
            "threads": 210,
            "ssh_password": "nope",
            "mysql": {"connections": 9, "token": "abc"},
            "notes": "ok",
        }
    )
    keys = [t["key"] for t in tiles]
    assert "qps" in keys
    assert "threads" in keys
    assert "mysql_connections" in keys
    assert "ssh_password" not in keys
    assert "mysql_token" not in keys
    assert all("password" not in t["key"] for t in tiles)


def test_flatten_payload_invalid():
    assert flatten_service_payload(None) == []
    assert flatten_service_payload("not-json") == []
    assert flatten_service_payload([]) == []


@patch("app.services.ai_insights_portal.settings")
def test_fetch_skips_without_url(mock_settings):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_ai_insights_extras()
    assert out["ok"] is False
    assert out["servers"] == []
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")
