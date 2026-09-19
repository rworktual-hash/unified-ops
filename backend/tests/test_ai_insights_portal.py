from unittest.mock import patch

from app.services.ai_insights_portal import (
    fetch_ai_insights_extras,
    flatten_service_payload,
    normalize_ai_group,
)


def test_normalize_ai_group():
    assert normalize_ai_group("AI-CCaaS-PBX-1", None, "pbx") == ("pbx", "PBX Signaling")
    assert normalize_ai_group("Redis-3", "redis", None) == ("redis", "Redis")
    assert normalize_ai_group("DR-GPU1-148", None, "gpu") == ("ai", "AI-Servers")
    assert normalize_ai_group("Ontology-Postgresql", None, "database") == ("postgres", "PostgreSQL")
    assert normalize_ai_group("AI-CCaaS-SGW-1", None, "sip") == ("sip", "SIP Gateway")
    assert normalize_ai_group("ccaas-vmg1", None, None) == ("voicemg", "VoiceMG Servers")


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
