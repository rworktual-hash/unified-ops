from datetime import date, datetime, timedelta

from unittest.mock import patch

from app.services.voicemg_portal import (
    _map_server,
    _prefixed,
    downsample_rows,
    fetch_voicemg_extras,
    fetch_voicemg_history,
    history_window,
    fleet_points,
    map_history_sample,
    mem_label,
    merge_host_series,
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


def test_map_server_utilization_fields():
    row = {
        "id": 3,
        "hostname": "ccaas-vmg2",
        "ip_address": "10.180.0.77",
        "product": "ccaas",
        "d_used_pct": 0.0,
        "n_rx_errors": 4,
        "n_rx_drops": 1,
        "p_open_fds": 812,
        "p_threads": 44,
        "i_sent_ps": 12.5,
        "i_recv_ps": 11.0,
        "i_latency_ms": 2.4,
        "k_runqueue": 3,
        "k_buffers_mb": 128,
        "c_udp_pps_in": 90,
        "c_udp_pps_out": 80,
        "n_rx_mbps": 1.2,
        "n_tx_mbps": 0.8,
        "p_cpu_pct": 18.0,
        "p_mem_pct": 9.5,
        "p_udp_sockets": 40,
        "c_rtp_gb": 1.5,
        "c_rtp_mbps_exp": 2.1,
    }
    out = _map_server(row)
    assert out["disk_used_pct"] == 0.0
    assert out["rx_errors"] == 4
    assert out["rx_drops"] == 1
    assert out["open_fds"] == 812
    assert out["threads"] == 44
    assert out["ipc_sent_ps"] == 12.5
    assert out["ipc_latency_ms"] == 2.4
    assert out["runqueue"] == 3
    assert out["udp_pps_in"] == 90
    assert out["nic_rx_mbps"] == 1.2
    assert out["proc_cpu_pct"] == 18.0
    assert out["udp_sockets"] == 40
    assert out["rtp_gb"] == 1.5
    assert out["rtp_mbps_exp"] == 2.1


def test_map_history_sample_utilization():
    out = map_history_sample(
        {
            "ts": datetime(2026, 9, 19, 12, 0, 0),
            "rx_errors": 2,
            "open_fds": 100,
            "sent_ps": 5,
            "recv_ps": 4,
            "latency_ms": 1.2,
            "udp_pps_in": 30,
            "nic_rx_mbps": 0.4,
            "proc_cpu_pct": 11,
            "rtp_bytes": 2_000_000_000,
            "disk_used_pct": 41,
            "rtp_mbps_exp": 3.3,
        }
    )
    assert out["rx_errors"] == 2
    assert out["open_fds"] == 100
    assert out["ipc_sent_ps"] == 5
    assert out["ipc_latency_ms"] == 1.2
    assert out["udp_pps_in"] == 30
    assert out["nic_rx_mbps"] == 0.4
    assert out["proc_cpu_pct"] == 11
    assert out["rtp_gb"] == 2.0
    assert out["disk_used_pct"] == 41
    assert out["rtp_mbps_exp"] == 3.3


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


def test_downsample_rows_keeps_ends():
    rows = [{"i": n} for n in range(10)]
    out = downsample_rows(rows, 3)
    assert out[0]["i"] == 0
    assert out[-1]["i"] == 9
    assert len(out) == 3


def test_map_history_sample_derives_loss_and_rtp():
    out = map_history_sample(
        {
            "ts": datetime(2026, 9, 19, 12, 0, 0),
            "active_calls": 4,
            "mos": 4.1,
            "rtp_mbps_out": 1.5,
            "rtp_mbps_in": 0.5,
            "pkts_sent_ps": 100,
            "pkts_recv_ps": 100,
            "pkts_lost_delta": 2,
        }
    )
    assert out["rtp_mbps"] == 2.0
    assert out["packet_loss_pct"] == 1.0
    assert out["active_calls"] == 4


def test_merge_and_fleet_history():
    ts = datetime(2026, 9, 19, 12, 0, 10)
    host_a = merge_host_series(
        [{"ts": ts, "active_calls": 3, "mos": 4.0, "rtp_mbps_out": 1, "rtp_mbps_in": 1}],
        [{"ts": ts, "cpu_pct": 20}],
        bucket_seconds=10,
    )
    host_b = merge_host_series(
        [{"ts": ts, "active_calls": 5, "mos": 4.4, "rtp_mbps_out": 2, "rtp_mbps_in": 0}],
        [{"ts": ts, "cpu_pct": 40}],
        bucket_seconds=10,
    )
    fleet = fleet_points([host_a, host_b])
    assert len(fleet) == 1
    assert fleet[0]["active_calls"] == 8
    assert fleet[0]["mos"] == 4.2
    assert fleet[0]["rtp_mbps"] == 4
    assert fleet[0]["cpu_pct"] == 30


def test_history_window_matches_old_portal():
    now = datetime(2026, 9, 19, 18, 30, 0)
    today = date(2026, 9, 19)
    since, until, bucket = history_window("yesterday", now, today)
    assert since == datetime(2026, 9, 18, 0, 0, 0)
    assert until == datetime(2026, 9, 18, 23, 59, 59)
    assert bucket == 300
    week_since, week_until, week_bucket = history_window("week", now, today)
    assert week_until == now
    assert week_since == now - timedelta(days=7)
    assert week_bucket == 1800
    custom_since, custom_until, _ = history_window(
        "custom",
        now,
        today,
        start=datetime(2026, 9, 10, 8, 0, 0),
        end=datetime(2026, 9, 12, 8, 0, 0),
    )
    assert custom_since == datetime(2026, 9, 10, 8, 0, 0)
    assert custom_until == datetime(2026, 9, 12, 8, 0, 0)


@patch("app.services.voicemg_portal.get_cached", return_value=None)
@patch("app.services.voicemg_portal.settings")
def test_history_skips_without_url(mock_settings, _cache):
    mock_settings.legacy_metrics_database_url = None
    out = fetch_voicemg_history("5m", "ai_ccaas")
    assert out["ok"] is False
    assert out["points"] == []
    assert out["range"] == "5m"
    assert out["group"] == "ai_ccaas"
    assert "LEGACY_METRICS_DATABASE_URL" in (out["reason"] or "")
