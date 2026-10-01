from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import CurrentUser, get_current_user
from app.api.llm_obs import dashboard_router, ingest_router
from app.db.session import Base, get_db
from app.models.llm_obs import LlmObsApiKey, LlmObsProject, LlmObsRun, LlmObsTrace
from app.schemas.llm_obs import IngestBody
from app.services.llm_obs import LlmObsConflict, create_api_key, create_project, ingest, match_api_key
from app.services.llm_obs_demo import DEMO_TRACE

ADMIN = CurrentUser(id=1, email="admin@worktual.tech", role="admin", is_active=True)
OTHER = CurrentUser(id=2, email="other@worktual.tech", role="user", is_active=True)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            LlmObsProject.__table__,
            LlmObsApiKey.__table__,
            LlmObsTrace.__table__,
            LlmObsRun.__table__,
        ],
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(session):
    app = FastAPI()
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(ingest_router, prefix="/api")

    def _db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    return TestClient(app)


def test_demo_project_trace_shows_agent_model_prompt_and_failed_tool(session):
    project = create_project(session, ADMIN, "trace-demo", "Trace demo")
    _key, raw = create_api_key(session, project, "demo")
    matched = match_api_key(session, raw)
    assert matched is not None
    result = ingest(session, matched, IngestBody.model_validate(DEMO_TRACE))

    assert result.project == "trace-demo"
    assert result.status == "error"
    assert result.run_count == 4

    from app.services.llm_obs import get_trace

    detail = get_trace(session, ADMIN, result.trace_id)
    assert detail is not None
    assert detail.agents == ["crm-support-agent"]
    assert detail.models == ["worktual-gemma"]
    assert detail.tools == ["lookup_contact", "create_ticket"]
    assert detail.failed_tools == ["create_ticket"]
    assert detail.total_tokens == 58

    by_name = {run.name: run for run in detail.runs}
    assert by_name["plan"].system_prompt.startswith("You are the CRM assistant")
    assert by_name["plan"].model == "worktual-gemma"
    assert by_name["lookup_contact"].status == "success"
    assert by_name["create_ticket"].status == "error"
    assert by_name["create_ticket"].error == "CRM API timeout after 30s"
    assert "should-not-store" not in (by_name["create_ticket"].input or "")
    assert "[redacted]" in (by_name["create_ticket"].input or "")
    assert detail.latency_ms == 2000


def test_raw_key_is_not_listed_and_revoked_key_cannot_ingest(session):
    project = create_project(session, ADMIN, "crm", "CRM")
    row, raw = create_api_key(session, project, "crm-prod")
    from app.services.llm_obs import list_api_keys, revoke_api_key

    listed = list_api_keys(session, project.id)
    assert listed[0].key_prefix == raw[:16]
    assert raw != listed[0].key_hash
    assert listed[0].key_prefix not in listed[0].key_hash

    revoke_api_key(session, project.id, row.id)
    assert match_api_key(session, raw) is None


def test_other_user_cannot_read_the_project(session):
    project = create_project(session, OTHER, "ticketing", "Ticketing")
    from app.services.llm_obs import get_owned_project

    assert get_owned_project(session, OTHER, project.id) is not None
    assert get_owned_project(session, CurrentUser(id=9, email="x@y.z", role="user", is_active=True), project.id) is None
    assert get_owned_project(session, ADMIN, project.id) is not None


def test_duplicate_trace_id_conflicts(session):
    project = create_project(session, ADMIN, "ccaas", "CCaaS")
    _row, raw = create_api_key(session, project, "ccaas")
    key = match_api_key(session, raw)
    body = IngestBody.model_validate(
        {
            "trace": {"id": "same", "name": "call"},
            "runs": [{"id": "a1", "type": "agent", "name": "voice-agent", "status": "success"}],
        }
    )
    ingest(session, key, body)
    with pytest.raises(LlmObsConflict):
        ingest(session, key, body)


def test_http_ingest_uses_api_key_not_user_login(client, session):
    created = client.post("/api/llm-obs/projects", json={"name": "trace-demo", "display_name": "Trace demo"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    key = client.post(f"/api/llm-obs/projects/{project_id}/keys", json={"name": "demo"})
    assert key.status_code == 201
    raw = key.json()["api_key"]
    assert raw.startswith("wllm_")

    listed = client.get(f"/api/llm-obs/projects/{project_id}/keys")
    assert listed.status_code == 200
    assert "api_key" not in listed.json()[0]
    assert raw not in listed.text

    denied = client.post("/api/llm-obs/ingest", json=DEMO_TRACE)
    assert denied.status_code == 401

    accepted = client.post(
        "/api/llm-obs/ingest",
        json=DEMO_TRACE,
        headers={"X-Api-Key": raw},
    )
    assert accepted.status_code == 201, accepted.text
    trace_id = accepted.json()["trace_id"]

    summary = client.get("/api/llm-obs/summary", params={"project_id": project_id, "status": "error"})
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 1
    assert body["error"] == 1
    assert body["total_tokens"] == 58
    assert "worktual-gemma" in body["models"]

    detail = client.get(f"/api/llm-obs/traces/{trace_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["failed_tools"] == ["create_ticket"]
    assert any(run["system_prompt"] and "CRM assistant" in run["system_prompt"] for run in payload["runs"])

    filtered = client.get(
        "/api/llm-obs/traces",
        params={"model": "missing-model", "from": "2026-10-01T00:00:00+00:00", "to": "2026-10-02T00:00:00+00:00"},
    )
    assert filtered.status_code == 200
    assert filtered.json() == []

    in_range = client.get(
        "/api/llm-obs/traces",
        params={"model": "worktual-gemma", "from": datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat()},
    )
    assert in_range.status_code == 200
    assert len(in_range.json()) == 1
