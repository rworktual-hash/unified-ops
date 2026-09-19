from unittest.mock import patch

from app.services.voicemg_portal import (
    _map_server,
    _prefixed,
    fetch_voicemg_extras,
    mem_label,
    product_group,
)


def test_prefixed_skips_id():
    assert _prefixed({"id": 3, "cpu_pct": 10, "load1": 0.2}, "sys_") == {
        "sys_cpu_pct": 10,
        "sys_load1": 0.2,
    }


def test_mem_label():
    assert mem_label(None, None) is None
    assert mem_label(1024, 8192) == "1024/8192 MB"
    assert mem_label(512.2, None) == "512.2 MB used"
    assert mem_label(None, 4096) == "4096 MB total"


def test_map_server_skips_missing_metrics():
    row = {
        "id": 7,
        "hostname": "ccaas-vmg1",
        "ip_address": "10.180.0.76",
        "product": "ccaas",
        "role": "vmg",
        "sys_cpu_pct": 12.4,
        "sys_load1": 0.35,
        "sys_mem_used_mb": 2048,
        "sys_mem_total_mb": 8192,
        "c_active_calls": 9,
        "c_rtp_sessions": 11,
        "c_rtp_mbps_out": 1.25,
        "c_rtp_mbps_in": 0.8,
        "c_jitter_ms": 3.2,
        "c_pkts_lost_delta": 0,
        "c_ts": "2026-09-19 10:00:00",
    }
    out = _map_server(row)
    assert out["ip"] == "10.180.0.76"
    assert out["ip_address"] == "10.180.0.76"
    assert out["hostname"] == "ccaas-vmg1"
    assert out["cpu_pct"] == 12.4
    assert out["active_calls"] == 9
    assert out["mem"] == "2048/8192 MB"
    assert out["rtp_mbps_out"] == 1.25
    assert "password" not in out
    assert "api_token" not in out
    assert out["group"] == "ccaas"


def test_product_group_ai_ccaas():
    assert product_group("ai-vmg1", "ccaas") == "ai_ccaas"
    assert product_group("QA-NewAIVMG", None) == "ai_ccaas"
    assert product_group("ccaas-stt1", "ccaas") == "ccaas"


def test_map_server_quality_fields():
    row = {
        "id": 2,
        "hostname": "ai-vmg1",
        "ip_address": "10.180.0.83",
        "product": "ai_ccaas",
        "c_active_calls": 6,
        "c_mos": 4.37,
        "c_pkt_loss_pct": 0.0,
        "c_quality_source": "rtcp",
        "c_stalled_udp": 2,
        "c_pkts_sent_ps": 100,
        "c_pkts_recv_ps": 100,
        "c_pkts_lost_delta": 0,
        "p_udp_active": 324,
        "p_udp_inactive": 2,
    }
    out = _map_server(row)
    assert out["group"] == "ai_ccaas"
    assert out["mos"] == 4.37
    assert out["stall"] == 2
    assert out["udp_active"] == 324
    assert out["packet_loss_pct"] == 0.0
    assert out["quality_source"] == "rtcp"
    assert out["rtcp"] == "rtcp"


@patch("app.services.voicemg_portal.settings")
def test_fetch_skips_without_url(mock_settings):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_voicemg_extras()
    assert out["ok"] is False
    assert out["servers"] == []
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")
