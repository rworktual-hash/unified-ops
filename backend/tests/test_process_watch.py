from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import CurrentUser, get_current_user
from app.api.process_watches import router
from app.db.session import Base, get_db
from app.models.process_watch import ProcessMailDefault, ProcessWatch
from app.monitoring.process_check import (
    ProcessCheckError,
    interpret_pgrep,
    listening_ports,
    matching_pids,
    pgrep_command,
    process_in_listing,
)
from app.services.process_mail import process_down_body, process_up_body
from app.schemas.process_watch import ProcessMailDefaults, ProcessWatchCreate, ProcessWatchUpdate
from app.services.process_watch import (
    ProcessWatchError,
    check_enabled_watches,
    check_watch,
    create_process_watch,
    set_default_recipients,
    update_process_watch,
)

ADMIN = CurrentUser(id=1, email="admin@worktual.tech", role="admin", is_active=True)
T0 = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
PASSWORD = "s3cret-pass"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[ProcessWatch.__table__, ProcessMailDefault.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(session, monkeypatch):
    monkeypatch.setattr("app.services.process_watch.probe_ssh_login", lambda **_kwargs: None)
    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("down", ""))
    app = FastAPI()
    app.include_router(router, prefix="/api")

    def _db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    return TestClient(app)


def _payload(**overrides):
    body = {
        "ip_address": "10.1.1.8",
        "ssh_port": 22,
        "ssh_username": "root",
        "ssh_password": PASSWORD,
        "label": "Edge nginx",
        "process_name": "nginx",
        "recipients": ["ops@example.com", "lead@example.com"],
        "check_interval": 60,
        "check_interval_unit": "seconds",
        "mail_interval_minutes": 5,
    }
    body.update(overrides)
    return body


def test_down_mail_uses_the_team_notice_in_ist():
    body = process_down_body(
        ip_address="10.180.1.244",
        process_name="stt_tts_mg",
        down_since="2026-10-30T14:05:30+00:00",
    )
    assert "Hello Team," in body
    assert "Service: stt_tts_mg" in body
    assert "Server IP: 10.180.1.244" in body
    assert "Status: DOWN" in body
    assert "Detected At: 30-Oct-2026 19:35:30 IST" in body
    assert "This is an automated notification. Please do not reply." in body


def test_up_mail_uses_the_team_notice_once_the_service_returns():
    body = process_up_body(
        ip_address="10.180.1.244",
        process_name="stt_tts_mg",
        restored_at="2026-10-30T14:10:00+00:00",
    )
    assert "Hello Team," in body
    assert "The following service is running again." in body
    assert "Service: stt_tts_mg" in body
    assert "Server IP: 10.180.1.244" in body
    assert "Status: UP" in body
    assert "Restored At: 30-Oct-2026 19:40:00 IST" in body
    assert "No further alerts will be sent until the service goes down again." in body
    assert "This is an automated notification. Please do not reply." in body


def test_pgrep_uses_the_process_name_and_empty_output_means_down():
    command = pgrep_command("srs")
    assert 'pgrep -x "srs"' in command
    assert "awk 'NR==1 {print $1}'" in command
    assert "__PGREP_UNAVAILABLE__" in command
    assert interpret_pgrep("44021\n") == ("pid", "44021")
    assert interpret_pgrep("") == ("down", "")
    assert interpret_pgrep("__PGREP_UNAVAILABLE__\n") == ("unavailable", "")

    with pytest.raises(ProcessCheckError):
        pgrep_command("nginx;rm")


def test_pgrep_pid_wins_and_a_miss_does_not_fall_back_to_ps(session, monkeypatch):
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()))

    def ps_must_not_run(_row):
        raise AssertionError("ps fallback")

    monkeypatch.setattr("app.services.process_watch.fetch_service_port", lambda **_kwargs: "5060")
    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("pid", "55"))
    monkeypatch.setattr("app.services.process_watch._fetch_listing", ps_must_not_run)
    check_watch(session, row, now=T0, force=True)
    assert row.status == "up"
    assert row.pid == "55"
    assert row.service_port == "5060"

    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("down", ""))
    check_watch(session, row, now=T0 + timedelta(seconds=60), force=True)
    assert row.status == "down"
    assert row.pid == ""

    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("unavailable", ""))
    monkeypatch.setattr(
        "app.services.process_watch._fetch_listing",
        lambda _row: "  77 nginx: master process nginx\n",
    )
    check_watch(session, row, now=T0 + timedelta(seconds=120), force=True)
    assert row.status == "up"
    assert row.pid == "77"


def test_listening_port_is_taken_from_the_pid_line():
    listing = "\n".join(
        [
            "State Recv-Q Send-Q Local Address:Port Peer Address:PortProcess",
            'LISTEN 0 128 0.0.0.0:5060 0.0.0.0:* users:(("pbx_mg",pid=2298672,fd=8))',
            'LISTEN 0 128 [::]:5060 [::]:* users:(("pbx_mg",pid=2298672,fd=9))',
            'LISTEN 0 128 0.0.0.0:80 0.0.0.0:* users:(("nginx",pid=101,fd=6))',
        ]
    )
    assert listening_ports(listing, "2298672") == "5060"
    assert listening_ports(listing, "101") == "80"
    assert listening_ports(listing, "999") == ""


def test_create_rejects_a_failed_ssh_login(session, monkeypatch):
    def fail(**_kwargs):
        raise ProcessCheckError("Authentication failed")

    monkeypatch.setattr("app.services.process_watch.probe_ssh_login", fail)
    with pytest.raises(ProcessWatchError, match="Authentication failed"):
        create_process_watch(session, ProcessWatchCreate.model_validate(_payload()), verify_ssh=True)
    assert session.query(ProcessWatch).count() == 0


def test_create_checks_the_process_after_ssh_login(session, monkeypatch):
    monkeypatch.setattr("app.services.process_watch.probe_ssh_login", lambda **_kwargs: None)
    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("pid", "55"))
    monkeypatch.setattr("app.services.process_watch.fetch_service_port", lambda **_kwargs: "5060")
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()), verify_ssh=True)
    assert row.status == "up"
    assert row.pid == "55"
    assert row.service_port == "5060"


def test_same_ip_and_port_cannot_be_added_twice(client):
    created = client.post("/api/process-watches", json=_payload())
    assert created.status_code == 201
    duplicate = client.post("/api/process-watches", json=_payload(label="Second"))
    assert duplicate.status_code == 422
    assert "IP and port" in duplicate.json()["detail"]

    other_port = client.post("/api/process-watches", json=_payload(label="Other port", ssh_port=4204))
    assert other_port.status_code == 201
    watch_id = created.json()["id"]
    renamed = client.patch(
        f"/api/process-watches/{watch_id}",
        json=_payload(label="Renamed", ssh_password=""),
    )
    assert renamed.status_code == 200
    clash = client.patch(
        f"/api/process-watches/{watch_id}",
        json=_payload(ssh_port=4204, ssh_password=""),
    )
    assert clash.status_code == 422


def test_process_listing_matches_the_name_and_ignores_the_ps_command():
    listing = "  42 ps -eo pid=,args=\n  101 nginx: master process nginx\n  202 postgres: writer\n"
    assert process_in_listing(listing, "nginx") is True
    assert process_in_listing(listing, "postgres") is True
    assert process_in_listing(listing, "redis") is False
    assert process_in_listing("ps -eo pid=,args=\n", "args") is False
    assert matching_pids(listing, "nginx") == ["101"]


def test_a_running_process_stores_its_pid(session):
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()))

    def listing(_row):
        return "  42 ps -eo pid=,args=\n  101 nginx: master process nginx\n  303 nginx: worker process\n"

    check_watch(session, row, now=T0, fetch=listing, send=lambda **_kwargs: None)
    assert row.status == "up"
    assert row.pid == "101, 303"

    def gone(_row):
        return "  202 postgres: writer\n"

    check_watch(session, row, now=T0 + timedelta(seconds=60), fetch=gone, send=lambda **_kwargs: None, force=True)
    assert row.status == "down"
    assert row.pid == ""


def test_additional_address_already_in_the_default_list_is_rejected(session):
    set_default_recipients(session, ProcessMailDefaults(recipients=["team@example.com"]))
    with pytest.raises(ProcessWatchError, match="team@example.com is already in the default mail ids"):
        create_process_watch(
            session,
            ProcessWatchCreate.model_validate(_payload(recipients=["Team@example.com", "lead@example.com"])),
        )
    row = create_process_watch(
        session,
        ProcessWatchCreate.model_validate(_payload(recipients=["lead@example.com"])),
    )
    with pytest.raises(ProcessWatchError, match="team@example.com is already in the default mail ids"):
        update_process_watch(
            session,
            row,
            ProcessWatchUpdate.model_validate(_payload(recipients=["team@example.com"], ssh_password="")),
        )


def test_alert_goes_to_the_default_list_and_the_additional_address(session):
    set_default_recipients(session, ProcessMailDefaults(recipients=["team@example.com"]))
    row = create_process_watch(
        session,
        ProcessWatchCreate.model_validate(_payload(recipients=["lead@example.com"])),
    )
    sent: list[dict] = []
    check_watch(session, row, now=T0, fetch=lambda _row: "", send=lambda **kwargs: sent.append(kwargs))
    assert sent[0]["recipients"] == ["team@example.com", "lead@example.com"]


def test_down_mail_repeats_on_the_interval_then_stops_when_the_process_returns(session):
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()))
    sent: list[dict] = []

    def listing(_row):
        return "postgres: writer\n"

    def send(**kwargs):
        sent.append(kwargs)

    check_watch(session, row, now=T0, fetch=listing, send=send)
    assert row.status == "down"
    assert row.down_since is not None
    assert len(sent) == 1
    assert sent[0]["recipients"] == ["ops@example.com", "lead@example.com"]

    check_watch(session, row, now=T0 + timedelta(minutes=2), fetch=listing, send=send)
    assert len(sent) == 1

    check_watch(session, row, now=T0 + timedelta(minutes=5), fetch=listing, send=send)
    assert len(sent) == 2

    def running(_row):
        return "nginx: master process nginx\n"

    check_watch(session, row, now=T0 + timedelta(minutes=10), fetch=running, send=send)
    assert row.status == "up"
    assert row.resolved_at is not None
    assert len(sent) == 3
    assert sent[-1]["restored_at"]

    check_watch(session, row, now=T0 + timedelta(minutes=20), fetch=running, send=send)
    assert len(sent) == 3


def test_ssh_failure_does_not_mark_the_process_down_or_send_mail(session):
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()))
    sent: list[dict] = []

    def fail(_row):
        raise ProcessCheckError("connection timed out")

    check_watch(session, row, now=T0, fetch=fail, send=lambda **kwargs: sent.append(kwargs))
    assert row.status == "unknown"
    assert row.last_error == "connection timed out"
    assert sent == []

    def absent(_row):
        return ""

    check_watch(session, row, now=T0, fetch=absent, send=lambda **kwargs: sent.append(kwargs), force=True)
    assert row.status == "down"
    assert len(sent) == 1

    check_watch(
        session,
        row,
        now=T0 + timedelta(minutes=1),
        fetch=fail,
        send=lambda **kwargs: sent.append(kwargs),
    )
    assert row.status == "down"
    assert row.last_error == "connection timed out"
    assert len(sent) == 1


def test_missing_smtp_records_down_and_says_mail_was_not_sent(session):
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()))
    check_watch(session, row, now=T0, fetch=lambda _row: "")
    assert row.status == "down"
    assert row.mail_sent is False
    assert row.mail_error == "Mail was not sent. SMTP is not configured."


def test_api_hides_the_password_and_rejects_a_bad_process_name(client):
    created = client.post("/api/process-watches", json=_payload())
    assert created.status_code == 201
    body = created.json()
    assert "ssh_password" not in body
    assert PASSWORD not in created.text
    assert body["status"] == "down"
    assert body["label"] == "Edge nginx"
    assert body["check_interval"] == 60
    assert body["check_interval_unit"] == "seconds"
    assert body["recipients"] == ["ops@example.com", "lead@example.com"]

    too_fast = client.post(
        "/api/process-watches",
        json=_payload(label="Too fast", check_interval=5, check_interval_unit="seconds"),
    )
    assert too_fast.status_code == 422

    listed = client.get("/api/process-watches")
    assert listed.status_code == 200
    assert PASSWORD not in listed.text
    assert "ssh_password" not in listed.text

    rejected = client.post("/api/process-watches", json=_payload(process_name="nginx;rm -rf"))
    assert rejected.status_code == 422


def test_edit_keeps_the_password_when_it_is_left_blank(client, session):
    created = client.post("/api/process-watches", json=_payload())
    watch_id = created.json()["id"]
    updated = client.patch(
        f"/api/process-watches/{watch_id}",
        json=_payload(label="Renamed", ssh_password=""),
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Renamed"
    assert PASSWORD not in updated.text
    row = session.get(ProcessWatch, watch_id)
    session.refresh(row)
    assert row.ssh_password == PASSWORD

    changed = client.patch(
        f"/api/process-watches/{watch_id}",
        json=_payload(ssh_password="new-secret"),
    )
    assert changed.status_code == 200
    assert "new-secret" not in changed.text
    session.refresh(row)
    assert row.ssh_password == "new-secret"


def test_api_check_reports_ssh_failure_without_marking_down(client, session, monkeypatch):
    row = create_process_watch(session, ProcessWatchCreate.model_validate(_payload()))
    watch_id = row.id

    def fail(**_kwargs):
        raise ProcessCheckError("SSH failed")

    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("unavailable", ""))
    monkeypatch.setattr("app.services.process_watch.fetch_process_listing", fail)
    checked = client.post(f"/api/process-watches/{watch_id}/check")
    assert checked.status_code == 200
    payload = checked.json()
    assert payload["status"] == "unknown"
    assert payload["last_error"] == "SSH failed"
    assert payload["mail_sent"] is None
    assert PASSWORD not in checked.text


def test_inactive_watch_is_not_monitored(client, session, monkeypatch):
    created = client.post(
        "/api/process-watches",
        json=_payload(description="Speech service on the edge"),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["description"] == "Speech service on the edge"
    assert body["enabled"] is True
    watch_id = body["id"]

    def running(**_kwargs):
        return "  101 nginx: master process nginx\n"

    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("unavailable", ""))
    monkeypatch.setattr("app.services.process_watch.fetch_service_port", lambda **_kwargs: "5060")
    monkeypatch.setattr("app.services.process_watch.fetch_process_listing", running)
    checked_up = client.post(f"/api/process-watches/{watch_id}/check?force=true")
    assert checked_up.json()["status"] == "up"
    assert checked_up.json()["pid"] == "101"
    assert checked_up.json()["service_port"] == "5060"

    updated = client.patch(
        f"/api/process-watches/{watch_id}",
        json=_payload(description="Speech service on the edge", enabled=False, ssh_password=""),
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["status"] == "unknown"
    assert updated.json()["pid"] == ""
    assert updated.json()["description"] == "Speech service on the edge"

    def fail(**_kwargs):
        raise AssertionError("inactive watch must not open SSH")

    monkeypatch.setattr("app.services.process_watch.fetch_process_listing", fail)
    checked = client.post(f"/api/process-watches/{watch_id}/check")
    assert checked.status_code == 200
    assert checked.json()["status"] == "unknown"
    assert checked.json()["last_error"] is None

    row = session.get(ProcessWatch, watch_id)
    session.refresh(row)
    result = check_enabled_watches(session, now=T0)
    assert result["checked"] == 0
    assert row.status == "unknown"


def test_automatic_check_waits_until_the_interval_and_manual_check_does_not(session):
    row = create_process_watch(
        session,
        ProcessWatchCreate.model_validate(_payload(check_interval=30, check_interval_unit="seconds")),
    )
    calls = {"n": 0}

    def listing(_row):
        calls["n"] += 1
        return "nginx: master process nginx\n"

    check_watch(session, row, now=T0, fetch=listing, force=True)
    checked_at = row.last_checked_at
    assert calls["n"] == 1

    check_watch(session, row, now=T0 + timedelta(seconds=5), fetch=listing)
    assert calls["n"] == 1
    assert row.last_checked_at == checked_at

    check_watch(session, row, now=T0 + timedelta(seconds=5), fetch=listing, force=True)
    assert calls["n"] == 2
    assert row.last_checked_at != checked_at


def test_scheduled_check_waits_for_the_watch_interval(session, monkeypatch):
    row = create_process_watch(
        session,
        ProcessWatchCreate.model_validate(_payload(check_interval=30, check_interval_unit="seconds")),
    )
    calls = {"n": 0}

    def listing(_row):
        calls["n"] += 1
        return "nginx: master process nginx\n"

    check_watch(session, row, now=T0, fetch=listing, send=lambda **_kwargs: None)
    assert calls["n"] == 1

    monkeypatch.setattr("app.services.process_watch._exact_pid", lambda _row: ("unavailable", ""))
    monkeypatch.setattr("app.services.process_watch._fetch_listing", listing)
    early = check_enabled_watches(session, now=T0 + timedelta(seconds=10))
    assert early["checked"] == 0
    assert calls["n"] == 1

    due = check_enabled_watches(session, now=T0 + timedelta(seconds=30))
    assert due["checked"] == 1
    assert calls["n"] == 2
