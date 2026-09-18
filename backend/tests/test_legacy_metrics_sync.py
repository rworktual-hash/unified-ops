from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.legacy_metrics_sync import (
    LegacyStreamConfig,
    _format_bytes,
    _metric_value,
    _parse_remote_time,
    _resolve_server_id,
    compute_legacy_overview,
    sync_legacy_stream,
)


def test_format_bytes():
    assert _format_bytes(None) is None
    assert _format_bytes(0) == "0.0 B"
    assert _format_bytes(1024) == "1.0 KB"
    assert _format_bytes(78 * 1024 * 1024) == "78.0 MB"


def test_metric_value_numeric_and_text():
    assert _metric_value(42) == (42.0, None)
    assert _metric_value("3.14") == (3.14, None)
    assert _metric_value("failed") == (None, "failed")
    assert _metric_value(None) == (None, None)


def test_parse_remote_time_naive():
    dt = _parse_remote_time(datetime(2026, 1, 1, 12, 0, 0))
    assert dt.tzinfo is not None


class TestResolveServerId:
    def test_match_by_ip(self):
        db = MagicMock()
        server = MagicMock(id=7, server_name="bv-90", ip_address="10.180.0.90")
        ip_query = MagicMock()
        ip_query.first.return_value = server
        project_query = MagicMock()
        project_query.filter.return_value = ip_query
        active_query = MagicMock()
        active_query.filter.return_value = project_query
        db.query.return_value.filter.return_value = active_query
        assert _resolve_server_id(db, domain="backupvault", host_value="10.180.0.90") == 7


class TestSyncLegacyStream:
    @patch("app.services.legacy_metrics_sync.settings")
    @patch("app.services.legacy_metrics_sync.get_legacy_metrics_engine")
    def test_skips_when_disabled(self, mock_engine, mock_settings):
        mock_settings.legacy_metrics_database_url = "mysql+pymysql://u:p@host/db"
        stream = LegacyStreamConfig(
            domain="backupvault",
            enabled=False,
            database="bv",
            table="jobs",
            col_id="id",
            col_time="t",
            col_host="host",
            metric_cols=("status",),
        )
        db = MagicMock()
        result = sync_legacy_stream(db, stream)
        assert result["skipped"] is True
        mock_engine.assert_not_called()


class TestComputeLegacyOverview:
    def test_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        out = compute_legacy_overview(db, domain="ai_insights", hours=24)
        assert out["point_count"] == 0
        assert out["distinct_hosts"] == 0
