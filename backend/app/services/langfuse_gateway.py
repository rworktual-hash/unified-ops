"""Server-side client for the self-hosted Langfuse OSS API.

Customer apps never see these credentials. Worktual sends one OpenTelemetry
trace per chat turn and reads it back through Observations API v2.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings

_TYPE_TO_LANGFUSE = {"agent": "agent", "llm": "generation", "tool": "tool", "chain": "chain"}
_TYPE_FROM_LANGFUSE = {
    "AGENT": "agent",
    "GENERATION": "llm",
    "TOOL": "tool",
    "CHAIN": "chain",
    "SPAN": "chain",
    "EVENT": "chain",
}


class LangfuseError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def enabled() -> bool:
    return bool(_host() and _public_key() and _secret_key())


def export_trace(
    *,
    project_name: str,
    project_id: int,
    external_id: str,
    trace_name: str,
    session_id: str | None,
    runs: list[Any],
) -> None:
    from app.services.llm_obs import _as_text, _aware, _system_from_input, redact_text

    trace_hex = _hex(f"{project_id}:{external_id}", 32)
    span_ids = {run.id: _hex(f"{trace_hex}:{run.id}", 16) for run in runs}
    spans = []
    for run in runs:
        started = _aware(run.started_at) or datetime.now(timezone.utc)
        finished = _aware(run.finished_at) or started
        system_prompt = run.system_prompt if (run.system_prompt or "").strip() else _system_from_input(run.input)
        system_prompt = redact_text(system_prompt)
        errored = run.status == "error" or bool((run.error or "").strip())
        usage = {
            "input": run.input_tokens or 0,
            "output": run.output_tokens or 0,
            "total": run.total_tokens if run.total_tokens is not None else (run.input_tokens or 0) + (run.output_tokens or 0),
        }
        has_usage = run.input_tokens is not None or run.output_tokens is not None or run.total_tokens is not None
        attributes: list[dict[str, Any]] = []
        _add(attributes, "langfuse.trace.name", trace_name)
        _add(attributes, "langfuse.environment", project_name)
        _add(attributes, "langfuse.session.id", (session_id or "").strip() or None)
        _add(attributes, "langfuse.observation.type", _TYPE_TO_LANGFUSE.get(run.type, "span"))
        _add(attributes, "langfuse.observation.input", redact_text(_as_text(run.input)))
        _add(attributes, "langfuse.observation.output", redact_text(_as_text(run.output)))
        _add(attributes, "langfuse.observation.level", "ERROR" if errored else "DEFAULT")
        _add(attributes, "langfuse.observation.status_message", redact_text(run.error) if errored else None)
        _add(attributes, "langfuse.observation.model.name", (run.model or "").strip() or None)
        _add(attributes, "langfuse.observation.metadata.system_prompt", system_prompt)
        _add(attributes, "langfuse.observation.metadata.worktual_run_id", run.id)
        _add(attributes, "langfuse.observation.metadata.worktual_parent_id", run.parent_id)
        _add(attributes, "langfuse.trace.metadata.worktual_trace_id", external_id)
        _add(attributes, "langfuse.trace.metadata.worktual_project", project_name)
        if has_usage:
            _add(attributes, "langfuse.observation.usage_details", json.dumps(usage))
        span: dict[str, Any] = {
            "traceId": trace_hex,
            "spanId": span_ids[run.id],
            "name": run.name,
            "startTimeUnixNano": _nano(started),
            "endTimeUnixNano": _nano(finished),
            "attributes": attributes,
        }
        if run.parent_id and run.parent_id in span_ids:
            span["parentSpanId"] = span_ids[run.parent_id]
        if errored:
            span["status"] = {"code": 2, "message": redact_text(run.error) or "error"}
        spans.append(span)
    payload = {
        "resourceSpans": [
            {
                "resource": {"attributes": [_string_attr("service.name", "worktual-llm-obs")]},
                "scopeSpans": [{"scope": {"name": "worktual-llm-obs"}, "spans": spans}],
            }
        ]
    }
    _request("POST", "/api/public/otel/v1/traces", payload, headers={"x-langfuse-ingestion-version": "4"})


def fetch_observations(
    *,
    started_from: datetime | None,
    started_to: datetime | None,
    environment: str | None = None,
    worktual_trace_id: str | None = None,
) -> list[dict[str, Any]]:
    end = started_to or (datetime.now(timezone.utc) + timedelta(days=1))
    start = started_from or (end - timedelta(days=30))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    query: dict[str, str] = {
        "fields": "core,basic,io,metadata,model,usage,metrics,trace_context",
        "limit": "200",
        "fromStartTime": start.isoformat(),
        "toStartTime": (end + timedelta(seconds=1)).isoformat(),
    }
    if environment:
        query["environment"] = environment
    if worktual_trace_id:
        query["filter"] = json.dumps(
            [
                {
                    "type": "stringObject",
                    "column": "metadata",
                    "key": "worktual_trace_id",
                    "operator": "=",
                    "value": worktual_trace_id,
                }
            ]
        )
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(10):
        page_query = dict(query)
        if cursor:
            page_query["cursor"] = cursor
        body = _request("GET", "/api/public/v2/observations", query=page_query)
        data = body.get("data") if isinstance(body, dict) else body
        if isinstance(data, list):
            rows.extend(item for item in data if isinstance(item, dict))
        meta = body.get("meta") if isinstance(body, dict) else None
        cursor = meta.get("cursor") if isinstance(meta, dict) else None
        if not cursor:
            break
    return rows


def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    url = _host() + path
    if query:
        url = url + "?" + urllib.parse.urlencode(query)
    token = b64encode(f"{_public_key()}:{_secret_key()}".encode()).decode()
    request_headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        raise LangfuseError(f"Langfuse returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LangfuseError("Langfuse is not reachable") from exc
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _host() -> str:
    return (settings.langfuse_host or "").strip().rstrip("/")


def _public_key() -> str:
    return (settings.langfuse_public_key or "").strip()


def _secret_key() -> str:
    return (settings.langfuse_secret_key or "").strip()


def _hex(text: str, size: int) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:size]


def _nano(value: datetime) -> str:
    return str(int(value.timestamp() * 1_000_000_000))


def _string_attr(key: str, value: str) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": value}}


def _add(attributes: list[dict[str, Any]], key: str, value: Any) -> None:
    if value is None or value == "":
        return
    attributes.append(_string_attr(key, value if isinstance(value, str) else str(value)))
