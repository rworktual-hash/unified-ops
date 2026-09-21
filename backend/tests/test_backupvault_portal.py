from datetime import date, datetime

from app.services.backupvault_portal import (
    classify_dest,
    format_bytes,
    map_incremental_row,
    map_repo_folder,
    parse_size_bytes,
    _calendar,
    _daily_counts,
    _group_tiers,
    _s3_totals,
)


def test_parse_and_format_sizes():
    assert parse_size_bytes("3400G") == 3400 * 1000**3
    assert parse_size_bytes("1.1T") == int(1.1 * 1000**4)
    assert parse_size_bytes(1024) == 1024
    assert format_bytes(1024) == "1.0 KB"


def test_classify_dest():
    assert classify_dest(path="/home/primary-db-backup/ccaas.sql.gz") == "primary"
    assert classify_dest(path="/secondary-db-backup/x.sql.gz") == "secondary"
    assert classify_dest(dest_type="s3") == "s3"
    assert classify_dest(role="Remote Onsite") == "remote"


def test_map_incremental_row():
    out = map_incremental_row(
        {
            "id": 4,
            "database_name": "CCAAS",
            "script": "ccaas_db_sync.sh",
            "status": "success",
            "last_success": datetime(2026, 9, 21, 6, 31, 32),
            "file_size_bytes": 2_000_000_000,
            "remote_path": "root@192.168.12.243:/home/worktual/ccaas",
        }
    )
    assert out["name"] == "CCAAS"
    assert out["script"] == "ccaas_db_sync.sh"
    assert out["status"] == "success"
    assert out["file_size_bytes"] == 2_000_000_000
    assert "192.168.12.243" in (out["remote_path"] or "")


def test_map_repo_and_group_tiers():
    folder = map_repo_folder(
        {
            "target_name": "CVM",
            "file_path": "/home/primary-db-backup/cvm-full.sql.gz",
            "file_size_bytes": 53_000_000,
            "started_at": datetime(2026, 9, 21, 1, 40, 10),
        }
    )
    assert folder["dest"] == "primary"
    assert folder["latest_file"] == "cvm-full.sql.gz"
    tiers = _group_tiers([folder])
    assert tiers[0]["id"] == "primary"
    assert tiers[0]["folder_count"] == 1


def test_calendar_and_history():
    today = date(2026, 9, 21)
    runs = [
        {"started_at": datetime(2026, 9, 21, 7, 0, 0), "status": "success"},
        {"started_at": datetime(2026, 9, 21, 8, 0, 0), "status": "failed"},
        {"started_at": datetime(2026, 9, 20, 7, 0, 0), "status": "success"},
    ]
    cal = _calendar(runs, today, 35)
    assert len(cal) == 35
    last = cal[-1]
    assert last["date"] == "2026-09-21"
    assert last["tone"] == "failed"
    assert last["success"] == 1
    hist = _daily_counts(runs, today, 14)
    assert hist[-1]["runs"] == 2
    assert hist[-2]["runs"] == 1


def test_s3_totals_from_transfers():
    total, objects = _s3_totals(
        [
            {"dest_type": "s3", "file_size_bytes": 1000, "object_count": 3},
            {"dest_type": "nfs", "file_size_bytes": 50},
        ],
        [],
    )
    assert total == 1000
    assert objects == 3
