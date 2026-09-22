from datetime import datetime
from unittest.mock import patch

from app.services.ai_insights_portal import (
    _metric_avgs,
    fetch_ai_insights_extras,
    fetch_ai_insights_history,
    flatten_service_payload,
    history_window,
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


def test_history_window_60m():
    now = datetime(2026, 9, 22, 11, 0, 0)
    since, until, bucket = history_window("60m", now, now.date())
    assert until == now
    assert since == datetime(2026, 9, 22, 10, 0, 0)
    assert bucket == 60
    hour_since, _, hour_bucket = history_window("1h", now, now.date())
    assert hour_since == since
    assert hour_bucket == 60


def test_metric_avgs_picks_known_columns():
    parts = _metric_avgs(["cpu_utilization", "mem_util", "gpu_temp", "password_hash"])
    joined = " ".join(parts)
    assert "cpu_utilization" in joined
    assert "memory_utilization" in joined
    assert "gpu_temperature" in joined
    assert "password" not in joined


@patch("app.services.ai_insights_portal.get_cached", return_value=None)
@patch("app.services.ai_insights_portal.settings")
def test_history_skips_without_url(mock_settings, _cache):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_ai_insights_history("60m", "ai")
    assert out["ok"] is False
    assert out["points"] == []
    assert out["range"] == "60m"
    assert out["group"] == "ai"
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")
