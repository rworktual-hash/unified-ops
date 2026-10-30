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
from app.models.process_watch import ProcessWatch
from app.monitoring.process_check import ProcessCheckError, process_in_listing
from app.schemas.process_watch import ProcessWatchCreate
from app.services.process_watch import check_watch, create_process_watch

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
    Base.metadata.create_all(engine, tables=[ProcessWatch.__table__])
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(session):
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
        "process_name": "nginx",
        "recipients": ["ops@example.com", "lead@example.com"],
        "mail_interval_minutes": 5,
    }
    body.update(overrides)
    return body


def test_process_listing_matches_the_name_and_ignores_the_ps_command():
    listing = "ps -eo args=\nnginx: master process nginx\npostgres: writer\n"
    assert process_in_listing(listing, "nginx") is True
    assert process_in_listing(listing, "postgres") is True
    assert process_in_listing(listing, "redis") is False
    assert process_in_listing("ps -eo args=\n", "args") is False


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

    check_watch(session, row, now=T0 + timedelta(minutes=20), fetch=running, send=send)
    assert len(sent) == 2


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

    check_watch(session, row, now=T0, fetch=absent, send=lambda **kwargs: sent.append(kwargs))
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
    assert body["status"] == "unknown"
    assert body["recipients"] == ["ops@example.com", "lead@example.com"]

    listed = client.get("/api/process-watches")
    assert listed.status_code == 200
    assert PASSWORD not in listed.text
    assert "ssh_password" not in listed.text

    rejected = client.post("/api/process-watches", json=_payload(process_name="nginx;rm -rf"))
    assert rejected.status_code == 422


def test_api_check_reports_ssh_failure_without_marking_down(client, monkeypatch):
    created = client.post("/api/process-watches", json=_payload())
    watch_id = created.json()["id"]

    def fail(**_kwargs):
        raise ProcessCheckError("SSH failed")

    monkeypatch.setattr("app.services.process_watch.fetch_process_listing", fail)
    checked = client.post(f"/api/process-watches/{watch_id}/check")
    assert checked.status_code == 200
    payload = checked.json()
    assert payload["status"] == "unknown"
    assert payload["last_error"] == "SSH failed"
    assert payload["mail_sent"] is None
    assert PASSWORD not in checked.text
