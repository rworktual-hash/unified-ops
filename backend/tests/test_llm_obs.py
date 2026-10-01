from datetime import datetime, timezone
import json

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


def test_worktual_ingest_reads_the_crm_flow_back_from_langfuse(client, session, monkeypatch):
    """Send the CRM demo through the Worktual endpoint and read the same flow from Langfuse."""
    import base64
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from app.config import settings
    from app.models.llm_obs import LlmObsTrace

    observations: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorized(self) -> bool:
            expected = "Basic " + base64.b64encode(b"pk-lf-test:sk-lf-test").decode()
            return self.headers.get("Authorization") == expected

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            if not self._authorized():
                self._send(401, {"message": "unauthorized"})
                return
            if not self.path.startswith("/api/public/otel/v1/traces"):
                self._send(404, {})
                return
            if self.headers.get("x-langfuse-ingestion-version") != "4":
                self._send(400, {"message": "missing ingestion version"})
                return
            observations.extend(_observations_from_otel(body))
            self._send(200, {})

        def do_GET(self) -> None:  # noqa: N802
            if not self._authorized():
                self._send(401, {"message": "unauthorized"})
                return
            if not self.path.split("?", 1)[0] == "/api/public/v2/observations":
                self._send(404, {})
                return
            self._send(200, {"data": observations, "meta": {"cursor": None}})

        def log_message(self, _format: str, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.setattr(settings, "langfuse_host", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    try:
        created = client.post("/api/llm-obs/projects", json={"name": "crm", "display_name": "CRM"})
        assert created.status_code == 201, created.text
        project_id = created.json()["id"]
        key = client.post(f"/api/llm-obs/projects/{project_id}/keys", json={"name": "crm"})
        assert key.status_code == 201, key.text
        raw = key.json()["api_key"]

        accepted = client.post("/api/llm-obs/ingest", json=DEMO_TRACE, headers={"X-Api-Key": raw})
        assert accepted.status_code == 201, accepted.text
        assert session.query(LlmObsTrace).count() == 1

        listed = client.get("/api/llm-obs/traces", params={"project_id": project_id})
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["id"] == "demo-crm-turn-1"
        assert rows[0]["session_id"] == "crm-billing-1"
        assert rows[0]["agents"] == ["crm-support-agent"]
        assert rows[0]["failed_tools"] == ["create_ticket"]
        assert "pk-lf" not in listed.text
        assert "sk-lf" not in listed.text

        detail = client.get("/api/llm-obs/traces/demo-crm-turn-1")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert "pk-lf" not in detail.text
        assert "sk-lf" not in detail.text
        assert [run["type"] for run in payload["runs"]] == ["agent", "llm", "tool", "tool"]
        assert [run["name"] for run in payload["runs"]] == [
            "crm-support-agent",
            "plan",
            "lookup_contact",
            "create_ticket",
        ]
        assert [run["parent_id"] for run in payload["runs"]] == [None, "agent-1", "agent-1", "agent-1"]
        plan = payload["runs"][1]
        assert plan["model"] == "worktual-gemma"
        assert "CRM assistant" in plan["system_prompt"]
        assert plan["input_tokens"] == 40
        assert plan["output_tokens"] == 18
        assert plan["total_tokens"] == 58
        assert plan["total_cost"] == 0.0025
        assert payload["runs"][2]["status"] == "success"
        assert payload["runs"][3]["status"] == "error"
        assert payload["runs"][3]["error"] == "CRM API timeout after 30s"
        assert "should-not-store" not in (payload["runs"][3]["input"] or "")
        assert "[redacted]" in (payload["runs"][3]["input"] or "")
        assert payload["session_id"] == "crm-billing-1"
        assert payload["latency_ms"] == 2000

        summary = client.get("/api/llm-obs/summary", params={"project_id": project_id})
        assert summary.status_code == 200, summary.text
        assert summary.json()["total"] == 1
        assert summary.json()["error"] == 1
        assert summary.json()["total_tokens"] == 58
        assert summary.json()["total_cost"] == 0.0025
        assert "worktual-gemma" in summary.json()["models"]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _observations_from_otel(body: dict) -> list[dict]:
    found: list[dict] = []
    for resource in body.get("resourceSpans", []):
        for scope in resource.get("scopeSpans", []):
            for span in scope.get("spans", []):
                attrs = {}
                for item in span.get("attributes", []):
                    value = item.get("value", {})
                    attrs[item["key"]] = value.get("stringValue", value.get("intValue"))
                meta = {}
                for key, value in attrs.items():
                    if key.startswith("langfuse.observation.metadata."):
                        meta[key.removeprefix("langfuse.observation.metadata.")] = value
                    elif key.startswith("langfuse.trace.metadata."):
                        meta[key.removeprefix("langfuse.trace.metadata.")] = value
                usage = {}
                raw_usage = attrs.get("langfuse.observation.usage_details")
                if isinstance(raw_usage, str) and raw_usage:
                    usage = json.loads(raw_usage)
                kind = str(attrs.get("langfuse.observation.type") or "span").upper()
                started = datetime.fromtimestamp(int(span["startTimeUnixNano"]) / 1_000_000_000, timezone.utc)
                finished = datetime.fromtimestamp(int(span["endTimeUnixNano"]) / 1_000_000_000, timezone.utc)
                row = {
                    "id": span["spanId"],
                    "traceId": span["traceId"],
                    "startTime": started.isoformat(),
                    "endTime": finished.isoformat(),
                    "type": kind,
                    "name": span["name"],
                    "level": attrs.get("langfuse.observation.level") or "DEFAULT",
                    "statusMessage": attrs.get("langfuse.observation.status_message"),
                    "environment": attrs.get("langfuse.environment"),
                    "sessionId": attrs.get("langfuse.session.id"),
                    "traceName": attrs.get("langfuse.trace.name"),
                    "input": attrs.get("langfuse.observation.input"),
                    "output": attrs.get("langfuse.observation.output"),
                    "model": attrs.get("langfuse.observation.model.name"),
                    "metadata": meta,
                    "usageDetails": usage,
                    "inputUsage": usage.get("input"),
                    "outputUsage": usage.get("output"),
                    "totalUsage": usage.get("total"),
                }
                if kind == "GENERATION" and usage:
                    row["totalCost"] = 0.0025
                found.append(row)
    return found
