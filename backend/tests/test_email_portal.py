from unittest.mock import patch

from app.services.email_portal import (
    fetch_email_extras,
    fold_status_counts,
    inventory_name,
    latest_queue_rows,
    map_event,
    parse_top_senders,
    sum_queue,
)


def test_fold_status_counts_normalizes():
    out = fold_status_counts(
        [
            ("sent", 10),
            ("bounce", 2),
            ("deferred", 3),
            ("host_not_reachable", 1),
            ("Delivered", 4),
            ("soft bounce", 1),
        ]
    )
    assert out["sent"] == 14
    assert out["bounce"] == 3
    assert out["deferred"] == 3
    assert out["host_not_reachable"] == 1


def test_parse_top_senders_json_and_csv():
    assert parse_top_senders('[{"sender":"a@b.com","count":9}]') == [{"sender": "a@b.com", "count": 9}]
    assert parse_top_senders("ops@worktual.com:4,alerts@x:2") == [
        {"sender": "ops@worktual.com", "count": 4},
        {"sender": "alerts@x", "count": 2},
    ]
    assert parse_top_senders({"a@b.com": 3}) == [{"sender": "a@b.com", "count": 3}]
    assert parse_top_senders(None) == []


def test_map_event_skips_secrets():
    out = map_event(
        {
            "id": 11,
            "log_datetime": "2026-09-21 10:00:00",
            "event_type": "delivered",
            "mail_from": "a@b.com",
            "mail_to": "c@d.com",
            "subject": "Hello",
            "direction": "out",
            "status": "sent",
            "dsn": "2.0.0",
            "server": "82.113.72.84",
            "server_name": "mail-1",
            "password": "nope",
            "raw_line": "should not be mapped",
        }
    )
    assert out["from_addr"] == "a@b.com"
    assert out["to_addr"] == "c@d.com"
    assert out["status"] == "sent"
    assert "password" not in out
    assert "raw_line" not in out


@patch("app.services.email_portal.settings")
def test_inventory_name_uses_host_map(mock_settings):
    mock_settings.email_mgmt_host_map = {"82.113.72.84": "email-mgmt-1"}
    assert inventory_name("82.113.72.84", "mail-1") == "email-mgmt-1"
    assert inventory_name(None, "mail-2") == "mail-2"
    assert inventory_name("campaign", "mail.worktual.pl") == "email-mgmt-1"
    assert inventory_name(None, "mail.worktual.pl") == "email-mgmt-1"


def test_latest_queue_and_sum():
    rows = latest_queue_rows(
        [
            {
                "id": 2,
                "server": "82.113.72.84",
                "server_name": "mail-1",
                "queue_count": 5,
                "deferred_count": 2,
                "active_count": 1,
                "incoming_count": 0,
                "snapshot_at": "2026-09-21 12:00:00",
                "top_senders": "[]",
            },
            {
                "id": 1,
                "server": "82.113.72.84",
                "server_name": "mail-1",
                "queue_count": 99,
                "deferred_count": 9,
                "active_count": 9,
                "incoming_count": 9,
                "snapshot_at": "2026-09-21 11:00:00",
            },
            {
                "id": 3,
                "server": "82.113.72.80",
                "server_name": "mail-2",
                "queue_count": 4,
                "deferred_count": 1,
                "active_count": 0,
                "incoming_count": 1,
                "snapshot_at": "2026-09-21 12:01:00",
            },
        ]
    )
    assert len(rows) == 2
    assert rows[0]["queue_count"] == 5
    summed = sum_queue(rows)
    assert summed["queue_count"] == 9
    assert summed["deferred_count"] == 3
    assert summed["incoming_count"] == 1


@patch("app.services.email_portal.get_cached", return_value=None)
@patch("app.services.email_portal.settings")
def test_fetch_skips_without_url(mock_settings, _cache):
    mock_settings.email_mgmt_database_url = None
    out = fetch_email_extras()
    assert out["ok"] is False
    assert out["servers"] == []
    assert out["events"] == []
    assert "EMAIL_MGMT_DATABASE_URL" in (out["reason"] or "")
