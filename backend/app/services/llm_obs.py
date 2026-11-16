from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.models.llm_obs import LlmObsApiKey, LlmObsProject, LlmObsRun, LlmObsTrace
from app.schemas.llm_obs import (
    IngestBody,
    IngestResult,
    RunPublic,
    SummaryPublic,
    TraceDetail,
    TraceListItem,
)
from app.services.app_auth import hash_password, verify_password
from app.services.langfuse_gateway import LangfuseError, _TYPE_FROM_LANGFUSE, enabled as langfuse_enabled
from app.services.langfuse_gateway import export_trace as langfuse_export
from app.services.langfuse_gateway import fetch_observations as langfuse_fetch

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SECRET_LINE = re.compile(
    r"""(password|secret|token|api[_-]?key|authorization|passwd)["']?\s*[:=]""",
    re.IGNORECASE,
)
_TEXT_LIMIT = 32000
_KEY_PREFIX_LEN = 16


class LlmObsRejected(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class LlmObsConflict(Exception):
    pass


class LlmObsUpstream(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def redact_text(value: str | None, limit: int = _TEXT_LIMIT) -> str | None:
    if value is None:
        return None
    lines = []
    for line in value.splitlines() or [""]:
        lines.append("[redacted]" if _SECRET_LINE.search(line) else line)
    text = "\n".join(lines)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str, ensure_ascii=False)


def _system_from_input(value: Any) -> str | None:
    messages = value if isinstance(value, list) else None
    if isinstance(value, dict):
        nested = value.get("messages")
        if isinstance(nested, list):
            messages = nested
    if not isinstance(messages, list):
        return None
    parts: list[str] = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") != "system":
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            parts.append(content)
    return "\n\n".join(parts) or None


def _latency(started: datetime | None, finished: datetime | None, given: int | None) -> int | None:
    if given is not None:
        return given
    if started is None or finished is None:
        return None
    return max(int((finished - started).total_seconds() * 1000), 0)


_ROLES = {"type 1": "Type 1", "type1": "Type 1", "type 2": "Type 2", "type2": "Type 2", "internal": "internal"}
_MODES = {"agent", "team", "orchestrator", "workflow"}


def _plain(value: str | None, limit: int, label: str) -> str:
    text = (value or "").strip()
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise LlmObsRejected(f"{label} is invalid.")
    return text


def _customer_role(value: str | None) -> str:
    text = _plain(value, 32, "Customer role")
    if not text:
        return ""
    role = _ROLES.get(text.lower().replace("_", " "))
    if role is None:
        raise LlmObsRejected("Customer role must be Type 1, Type 2, or internal.")
    return role


def _agent_mode(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    if text not in _MODES:
        raise LlmObsRejected("Agent mode must be agent, team, orchestrator, or workflow.")
    return text


def _filter_text(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return text[:limit].lower()


def _tokens(input_tokens: int | None, output_tokens: int | None, total_tokens: int | None) -> int | None:
    if total_tokens is not None:
        return total_tokens
    if input_tokens is None and output_tokens is None:
        return None
    return (input_tokens or 0) + (output_tokens or 0)


def visible_project_query(db: Session, user: CurrentUser):
    query = db.query(LlmObsProject)
    if user.role != "admin":
        query = query.filter(LlmObsProject.created_by_user_id == user.id)
    return query


def list_projects(db: Session, user: CurrentUser) -> list[LlmObsProject]:
    return visible_project_query(db, user).order_by(LlmObsProject.name).all()


def get_owned_project(db: Session, user: CurrentUser, project_id: int) -> LlmObsProject | None:
    return visible_project_query(db, user).filter(LlmObsProject.id == project_id).first()


def create_project(db: Session, user: CurrentUser, name: str, display_name: str | None) -> LlmObsProject:
    slug = name.strip().lower()
    if not _NAME.fullmatch(slug):
        raise LlmObsRejected("Project name must be lowercase letters, numbers, and hyphens.")
    if db.query(LlmObsProject).filter(LlmObsProject.name == slug).first():
        raise LlmObsConflict()
    row = LlmObsProject(
        name=slug,
        display_name=(display_name or slug).strip()[:128] or slug,
        created_by_user_id=user.id or None,
        created_at=_now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise LlmObsConflict() from None
    db.refresh(row)
    return row


def create_api_key(db: Session, project: LlmObsProject, name: str) -> tuple[LlmObsApiKey, str]:
    raw = "wllm_" + secrets.token_urlsafe(32)
    row = LlmObsApiKey(
        project_id=project.id,
        name=name.strip()[:128] or "default",
        key_prefix=raw[:_KEY_PREFIX_LEN],
        key_hash=hash_password(raw),
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def list_api_keys(db: Session, project_id: int) -> list[LlmObsApiKey]:
    return (
        db.query(LlmObsApiKey)
        .filter(LlmObsApiKey.project_id == project_id)
        .order_by(LlmObsApiKey.created_at.desc())
        .all()
    )


def revoke_api_key(db: Session, project_id: int, key_id: int) -> LlmObsApiKey | None:
    row = (
        db.query(LlmObsApiKey)
        .filter(LlmObsApiKey.id == key_id, LlmObsApiKey.project_id == project_id)
        .first()
    )
    if row is None:
        return None
    if row.revoked_at is None:
        row.revoked_at = _now()
        db.commit()
        db.refresh(row)
    return row


def match_api_key(db: Session, raw: str) -> LlmObsApiKey | None:
    token = raw.strip()
    if not token.startswith("wllm_") or len(token) < _KEY_PREFIX_LEN:
        return None
    rows = (
        db.query(LlmObsApiKey)
        .filter(LlmObsApiKey.key_prefix == token[:_KEY_PREFIX_LEN], LlmObsApiKey.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        try:
            ok = verify_password(token, row.key_hash)
        except ValueError:
            ok = False
        if ok:
            return row
    return None


def ingest(db: Session, key: LlmObsApiKey, body: IngestBody) -> IngestResult:
    ids = [run.id for run in body.runs]
    if len(ids) != len(set(ids)):
        raise LlmObsRejected("Each run id must be unique in the trace.")
    known = set(ids)
    parents = {run.id: run.parent_id for run in body.runs}
    for run in body.runs:
        if run.parent_id is not None and run.parent_id not in known:
            raise LlmObsRejected(f"parent_id {run.parent_id} does not match a run in this trace.")
        seen: set[str] = set()
        node: str | None = run.id
        while node is not None:
            if node in seen:
                raise LlmObsRejected("Run parents cannot form a cycle.")
            seen.add(node)
            node = parents.get(node)

    started = _aware(body.trace.started_at)
    finished = _aware(body.trace.finished_at)
    run_starts = [_aware(run.started_at) for run in body.runs if run.started_at]
    run_ends = [_aware(run.finished_at) for run in body.runs if run.finished_at]
    if started is None:
        started = min(run_starts) if run_starts else _now()
    if finished is None and run_ends:
        finished = max(run_ends)

    run_errors = [run for run in body.runs if run.status == "error" or (run.error or "").strip()]
    status = body.trace.status or ("error" if run_errors else "success")
    error = redact_text(body.trace.error)
    if error is None and run_errors:
        error = redact_text(run_errors[0].error or f"{run_errors[0].name} failed")

    external_id = (body.trace.id or uuid.uuid4().hex)[:64]
    customer = _plain(body.trace.customer, 128, "Customer")
    customer_role = _customer_role(body.trace.customer_role)
    agent_mode = _agent_mode(body.trace.agent_mode)
    agent_name = _plain(body.trace.agent, 128, "Agent name")
    if not agent_name:
        agent_name = next((run.name.strip()[:128] for run in body.runs if run.type == "agent" and run.name.strip()), "")
    session_id = (body.trace.session_id or "").strip()[:200] or None
    if langfuse_enabled():
        try:
            langfuse_export(
                project_name=key.project.name,
                project_id=key.project_id,
                external_id=external_id,
                trace_name=body.trace.name.strip()[:160],
                session_id=session_id,
                runs=body.runs,
                customer=customer,
                customer_role=customer_role,
                agent_name=agent_name,
                agent_mode=agent_mode,
            )
        except LangfuseError as exc:
            raise LlmObsUpstream(exc.message) from exc
    trace = LlmObsTrace(
        project_id=key.project_id,
        external_id=external_id,
        name=body.trace.name.strip()[:160],
        status=status,
        error_message=error,
        started_at=started,
        finished_at=finished,
        latency_ms=_latency(started, finished, None),
        session_id=session_id,
        customer=customer,
        customer_role=customer_role,
        agent_name=agent_name,
        agent_mode=agent_mode,
        created_at=_now(),
    )
    project_name = key.project.name
    now = _now()
    try:
        db.add(trace)
        db.flush()
        for run in body.runs:
            run_started = _aware(run.started_at)
            run_finished = _aware(run.finished_at)
            system_prompt = run.system_prompt if (run.system_prompt or "").strip() else None
            if system_prompt is None and (run.instructions or "").strip():
                system_prompt = run.instructions
            if system_prompt is None:
                system_prompt = _system_from_input(run.input)
            source = (run.tool_source or "").strip()
            if run.type != "tool":
                source = ""
            connector = (run.connector or "").strip()[:128] if run.type == "tool" else ""
            db.add(
                LlmObsRun(
                    trace_id=trace.id,
                    external_id=run.id,
                    parent_external_id=run.parent_id,
                    run_type=run.type,
                    name=run.name.strip()[:128],
                    model_name=(run.model or "").strip()[:128] or None,
                    system_prompt=redact_text(system_prompt),
                    input_text=redact_text(_as_text(run.input)),
                    output_text=redact_text(_as_text(run.output)),
                    status="error" if run.status == "error" or (run.error or "").strip() else "success",
                    error_message=redact_text(run.error),
                    started_at=run_started,
                    finished_at=run_finished,
                    latency_ms=_latency(run_started, run_finished, run.latency_ms),
                    input_tokens=run.input_tokens,
                    output_tokens=run.output_tokens,
                    total_tokens=_tokens(run.input_tokens, run.output_tokens, run.total_tokens),
                    tool_source=source,
                    connector=connector,
                    created_at=now,
                )
            )
        key.last_used_at = now
        db.commit()
    except IntegrityError:
        db.rollback()
        raise LlmObsConflict() from None
    db.refresh(trace)
    return IngestResult(
        trace_id=trace.id,
        external_id=trace.external_id,
        project=project_name,
        status=trace.status,
        run_count=len(body.runs),
    )


def _owned_trace_ids(db: Session, user: CurrentUser):
    return visible_project_query(db, user).with_entities(LlmObsProject.id)


def _filtered_traces(
    db: Session,
    user: CurrentUser,
    *,
    project_id: int | None,
    model: str | None,
    status: str | None,
    started_from: datetime | None,
    started_to: datetime | None,
    customer: str | None = None,
    agent: str | None = None,
    skill: str | None = None,
    tool: str | None = None,
):
    query = db.query(LlmObsTrace).filter(LlmObsTrace.project_id.in_(_owned_trace_ids(db, user)))
    if project_id is not None:
        query = query.filter(LlmObsTrace.project_id == project_id)
    if status in {"success", "error"}:
        query = query.filter(LlmObsTrace.status == status)
    if started_from is not None:
        query = query.filter(LlmObsTrace.started_at >= _aware(started_from))
    if started_to is not None:
        query = query.filter(LlmObsTrace.started_at <= _aware(started_to))
    if model:
        matching = db.query(LlmObsRun.trace_id).filter(LlmObsRun.model_name == model)
        query = query.filter(LlmObsTrace.id.in_(matching))
    customer_name = _filter_text(customer, 128)
    if customer_name:
        query = query.filter(func.lower(LlmObsTrace.customer) == customer_name)
    agent_name = _filter_text(agent, 128)
    if agent_name:
        agent_runs = db.query(LlmObsRun.trace_id).filter(
            LlmObsRun.run_type == "agent",
            func.lower(LlmObsRun.name) == agent_name,
        )
        query = query.filter(or_(func.lower(LlmObsTrace.agent_name) == agent_name, LlmObsTrace.id.in_(agent_runs)))
    skill_name = _filter_text(skill, 128)
    if skill_name:
        skill_runs = db.query(LlmObsRun.trace_id).filter(
            LlmObsRun.run_type == "skill",
            func.lower(LlmObsRun.name) == skill_name,
        )
        query = query.filter(LlmObsTrace.id.in_(skill_runs))
    tool_name = _filter_text(tool, 128)
    if tool_name:
        tool_runs = db.query(LlmObsRun.trace_id).filter(
            LlmObsRun.run_type == "tool",
            func.lower(LlmObsRun.name) == tool_name,
        )
        query = query.filter(LlmObsTrace.id.in_(tool_runs))
    return query


def _unique(names) -> list[str]:
    found: list[str] = []
    for name in names:
        if name and name not in found:
            found.append(name)
    return found


def model_options(db: Session, user: CurrentUser, project_id: int | None) -> list[str]:
    query = (
        db.query(LlmObsRun.model_name)
        .join(LlmObsTrace, LlmObsTrace.id == LlmObsRun.trace_id)
        .filter(LlmObsTrace.project_id.in_(_owned_trace_ids(db, user)))
        .filter(LlmObsRun.model_name.is_not(None))
    )
    if project_id is not None:
        query = query.filter(LlmObsTrace.project_id == project_id)
    return sorted({name for (name,) in query.distinct().all() if name})


def _scoped_traces(db: Session, user: CurrentUser, project_id: int | None):
    query = db.query(LlmObsTrace).filter(LlmObsTrace.project_id.in_(_owned_trace_ids(db, user)))
    if project_id is not None:
        query = query.filter(LlmObsTrace.project_id == project_id)
    return query


def request_options(db: Session, user: CurrentUser, project_id: int | None) -> dict[str, list[str]]:
    scoped = _scoped_traces(db, user, project_id)
    customers = sorted(
        {
            name
            for (name,) in scoped.with_entities(LlmObsTrace.customer).distinct().all()
            if name
        }
    )
    agents = sorted(
        {
            name
            for (name,) in scoped.with_entities(LlmObsTrace.agent_name).distinct().all()
            if name
        }
    )
    joined = db.query(LlmObsRun.name, LlmObsRun.run_type).join(LlmObsTrace, LlmObsTrace.id == LlmObsRun.trace_id)
    joined = joined.filter(LlmObsTrace.id.in_(scoped.with_entities(LlmObsTrace.id)))
    skills: set[str] = set()
    tools: set[str] = set()
    for name, run_type in joined.distinct().all():
        if not name:
            continue
        if run_type == "skill":
            skills.add(name)
        elif run_type == "tool":
            tools.add(name)
        elif run_type == "agent":
            agents.append(name) if name not in agents else None
    return {
        "customers": customers,
        "agents": sorted(set(agents)),
        "skills": sorted(skills),
        "tools": sorted(tools),
    }


def _trace_items(db: Session, traces: list[LlmObsTrace]) -> list[TraceListItem]:
    if not traces:
        return []
    project_ids = {trace.project_id for trace in traces}
    names = {
        row.id: row.display_name
        for row in db.query(LlmObsProject).filter(LlmObsProject.id.in_(project_ids)).all()
    }
    trace_ids = [trace.id for trace in traces]
    runs = db.query(LlmObsRun).filter(LlmObsRun.trace_id.in_(trace_ids)).all()
    by_trace: dict[int, list[LlmObsRun]] = {}
    for run in runs:
        by_trace.setdefault(run.trace_id, []).append(run)

    items: list[TraceListItem] = []
    for trace in traces:
        group = by_trace.get(trace.id, [])
        agents = _unique(run.name for run in group if run.run_type == "agent")
        skills = _unique(run.name for run in group if run.run_type == "skill")
        tools = _unique(run.name for run in group if run.run_type == "tool")
        failed = _unique(run.name for run in group if run.run_type == "tool" and run.status == "error")
        models = []
        tokens = 0
        for run in group:
            if run.model_name and run.model_name not in models:
                models.append(run.model_name)
            if run.run_type == "llm" and run.total_tokens:
                tokens += run.total_tokens
        items.append(
            TraceListItem(
                id=trace.id,
                project_id=trace.project_id,
                project=names.get(trace.project_id, ""),
                name=trace.name,
                status=trace.status,
                error=trace.error_message,
                started_at=trace.started_at,
                finished_at=trace.finished_at,
                latency_ms=trace.latency_ms,
                agents=agents,
                tools=tools,
                failed_tools=failed,
                models=models,
                total_tokens=tokens,
                run_count=len(group),
                session_id=trace.session_id,
                customer=trace.customer or "",
                customer_role=trace.customer_role or "",
                agent_name=trace.agent_name or (agents[0] if agents else ""),
                agent_mode=trace.agent_mode or "",
                skills=skills,
            )
        )
    return items


def _parse_stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _usage_count(usage: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        number = _number(usage.get(key))
        if number is not None:
            return int(number)
    return None


def _observation_runs(rows: list[dict[str, Any]]) -> list[RunPublic]:
    prepared: list[tuple[datetime, RunPublic]] = []
    for index, row in enumerate(rows, start=1):
        meta = _object(row.get("metadata"))
        usage = _object(row.get("usageDetails"))
        started = _parse_stamp(row.get("startTime"))
        finished = _parse_stamp(row.get("endTime"))
        latency = _latency(started, finished, None)
        if latency is None:
            seconds = _number(row.get("latency"))
            latency = int(seconds * 1000) if seconds is not None else None
        level = str(row.get("level") or "").upper()
        message = row.get("statusMessage")
        error = message.strip() if isinstance(message, str) and message.strip() else None
        recorded_type = str(meta.get("worktual_run_type") or "")
        kind = recorded_type if recorded_type in {"agent", "llm", "tool", "skill", "chain"} else _TYPE_FROM_LANGFUSE.get(str(row.get("type") or "").upper(), "chain")
        tool_source = str(meta.get("worktual_tool_source") or "") if kind == "tool" else ""
        connector = str(meta.get("worktual_connector") or "") if kind == "tool" else ""
        input_tokens = _usage_count(usage, "input", "input_tokens")
        if input_tokens is None:
            counted = _number(row.get("inputUsage"))
            input_tokens = int(counted) if counted is not None else None
        output_tokens = _usage_count(usage, "output", "output_tokens")
        if output_tokens is None:
            counted = _number(row.get("outputUsage"))
            output_tokens = int(counted) if counted is not None else None
        total_tokens = _usage_count(usage, "total", "total_tokens")
        if total_tokens is None:
            counted = _number(row.get("totalUsage"))
            total_tokens = int(counted) if counted is not None else _tokens(input_tokens, output_tokens, None)
        prompt = meta.get("system_prompt")
        system_prompt = prompt.strip() if isinstance(prompt, str) and prompt.strip() else None
        run_id = meta.get("worktual_run_id")
        parent = meta.get("worktual_parent_id")
        model = row.get("model")
        prepared.append(
            (
                started or datetime.min.replace(tzinfo=timezone.utc),
                RunPublic(
                    id=index,
                    external_id=str(run_id or row.get("id") or index),
                    parent_id=str(parent) if parent else None,
                    type=kind,
                    name=str(row.get("name") or "step")[:128],
                    model=str(model).strip() if isinstance(model, str) and model.strip() else None,
                    system_prompt=system_prompt,
                    input=row.get("input") if isinstance(row.get("input"), str) else _as_text(row.get("input")),
                    output=row.get("output") if isinstance(row.get("output"), str) else _as_text(row.get("output")),
                    status="error" if level == "ERROR" or error else "success",
                    error=error,
                    started_at=started,
                    finished_at=finished,
                    latency_ms=latency,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    total_cost=_number(row.get("totalCost")),
                    tool_source=tool_source if tool_source in {"builtin", "mcp"} else "",
                    connector=connector[:128],
                ),
            )
        )
    prepared.sort(key=lambda item: (item[0], item[1].id))
    return [run for _stamp, run in prepared]


def _langfuse_details(
    db: Session,
    user: CurrentUser,
    *,
    project_id: int | None,
    model: str | None,
    status: str | None,
    started_from: datetime | None,
    started_to: datetime | None,
    trace_key: str | None = None,
) -> list[TraceDetail]:
    owned = list_projects(db, user)
    if project_id is not None:
        owned = [project for project in owned if project.id == project_id]
    by_name = {project.name: project for project in owned}
    if not by_name:
        return []
    environment = owned[0].name if project_id is not None and len(owned) == 1 else None
    rows = langfuse_fetch(
        started_from=_aware(started_from),
        started_to=_aware(started_to),
        environment=environment,
        worktual_trace_id=trace_key,
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        meta = _object(row.get("metadata"))
        external = meta.get("worktual_trace_id")
        project_name = row.get("environment") or meta.get("worktual_project")
        if not isinstance(external, str) or not external or not isinstance(project_name, str):
            continue
        if project_name not in by_name:
            continue
        if trace_key is not None and external != trace_key:
            continue
        grouped.setdefault((project_name, external), []).append(row)

    details: list[TraceDetail] = []
    for (project_name, external), group in grouped.items():
        project = by_name[project_name]
        runs = _observation_runs(group)
        if model and model not in {run.model for run in runs if run.model}:
            continue
        failed = [run for run in runs if run.status == "error"]
        trace_status = "error" if failed else "success"
        if status in {"success", "error"} and trace_status != status:
            continue
        starts = [run.started_at for run in runs if run.started_at]
        ends = [run.finished_at for run in runs if run.finished_at]
        started = min(starts) if starts else _now()
        finished = max(ends) if ends else None
        names = []
        tokens = 0
        costs: list[float] = []
        for run in runs:
            if run.model and run.model not in names:
                names.append(run.model)
            if run.type == "llm" and run.total_tokens:
                tokens += run.total_tokens
            if run.total_cost is not None:
                costs.append(run.total_cost)
        session = next((str(row.get("sessionId")) for row in group if row.get("sessionId")), None)
        trace_name = next((str(row.get("traceName")) for row in group if row.get("traceName")), external)
        details.append(
            TraceDetail(
                id=external,
                project_id=project.id,
                project=project.display_name,
                name=trace_name,
                status=trace_status,
                error=failed[0].error if failed else None,
                started_at=started,
                finished_at=finished,
                latency_ms=_latency(started, finished, None),
                agents=_unique(run.name for run in runs if run.type == "agent"),
                tools=_unique(run.name for run in runs if run.type == "tool"),
                failed_tools=_unique(run.name for run in runs if run.type == "tool" and run.status == "error"),
                skills=_unique(run.name for run in runs if run.type == "skill"),
                models=names,
                total_tokens=tokens,
                run_count=len(runs),
                session_id=session,
                total_cost=sum(costs) if costs else None,
                runs=runs,
            )
        )
    details.sort(key=lambda item: item.started_at, reverse=True)
    return details[:200]


def _matches_request(
    item: TraceDetail,
    *,
    customer: str | None,
    agent: str | None,
    skill: str | None,
    tool: str | None,
) -> bool:
    customer_name = _filter_text(customer, 128)
    if customer_name and item.customer.lower() != customer_name:
        return False
    agent_name = _filter_text(agent, 128)
    if agent_name and agent_name not in {item.agent_name.lower(), *(name.lower() for name in item.agents)}:
        return False
    skill_name = _filter_text(skill, 128)
    if skill_name and skill_name not in {name.lower() for name in item.skills}:
        return False
    tool_name = _filter_text(tool, 128)
    if tool_name and tool_name not in {name.lower() for name in item.tools}:
        return False
    return True


def _summary_from_details(
    details: list[TraceDetail],
    *,
    models: list[str],
    customers: list[str],
    agents: list[str],
    skills: list[str],
    tools: list[str],
) -> SummaryPublic:
    success = sum(1 for item in details if item.status == "success")
    latencies = [item.latency_ms for item in details if item.latency_ms is not None]
    costs = [item.total_cost for item in details if item.total_cost is not None]
    return SummaryPublic(
        total=len(details),
        success=success,
        error=len(details) - success,
        avg_latency_ms=int(sum(latencies) / len(latencies)) if latencies else None,
        total_tokens=sum(item.total_tokens for item in details),
        total_cost=sum(costs) if costs else None,
        models=models,
        customers=customers,
        agents=agents,
        skills=skills,
        tools=tools,
    )


def _overlay_local(db: Session, details: list[TraceDetail]) -> list[TraceDetail]:
    external_ids = [str(item.id) for item in details]
    if not external_ids:
        return details
    rows = db.query(LlmObsTrace).filter(LlmObsTrace.external_id.in_(external_ids)).all()
    if not rows:
        return details
    by_external: dict[str, list[LlmObsTrace]] = {}
    for row in rows:
        by_external.setdefault(row.external_id, []).append(row)
    grouped: dict[int, list[LlmObsRun]] = {}
    for run in db.query(LlmObsRun).filter(LlmObsRun.trace_id.in_([row.id for row in rows])).all():
        grouped.setdefault(run.trace_id, []).append(run)
    overlaid: list[TraceDetail] = []
    for item in details:
        matches = by_external.get(str(item.id), [])
        row = next((candidate for candidate in matches if candidate.project_id == item.project_id), None)
        if row is None:
            overlaid.append(item)
            continue
        group = grouped.get(row.id, [])
        costs = {run.external_id: run.total_cost for run in item.runs}
        local_runs = [
            RunPublic(
                id=run.id,
                external_id=run.external_id,
                parent_id=run.parent_external_id,
                type=run.run_type,
                name=run.name,
                model=run.model_name,
                system_prompt=run.system_prompt,
                input=run.input_text,
                output=run.output_text,
                status=run.status,
                error=run.error_message,
                started_at=run.started_at,
                finished_at=run.finished_at,
                latency_ms=run.latency_ms,
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                total_tokens=run.total_tokens,
                total_cost=costs.get(run.external_id),
                tool_source=run.tool_source or "",
                connector=run.connector or "",
            )
            for run in sorted(group, key=lambda run: (run.started_at or datetime.min.replace(tzinfo=timezone.utc), run.id))
        ]
        overlaid.append(
            item.model_copy(
                update={
                    "customer": row.customer or item.customer,
                    "customer_role": row.customer_role or item.customer_role,
                    "agent_name": row.agent_name or item.agent_name,
                    "agent_mode": row.agent_mode or item.agent_mode,
                    "skills": _unique(run.name for run in group if run.run_type == "skill") or item.skills,
                    "tools": _unique(run.name for run in group if run.run_type == "tool") or item.tools,
                    "session_id": row.session_id or item.session_id,
                    "runs": local_runs or item.runs,
                }
            )
        )
    return overlaid


def list_traces(
    db: Session,
    user: CurrentUser,
    *,
    project_id: int | None,
    model: str | None,
    status: str | None,
    started_from: datetime | None,
    started_to: datetime | None,
    customer: str | None = None,
    agent: str | None = None,
    skill: str | None = None,
    tool: str | None = None,
) -> list[TraceListItem]:
    if langfuse_enabled():
        try:
            details = _langfuse_details(
                db,
                user,
                project_id=project_id,
                model=model,
                status=status,
                started_from=started_from,
                started_to=started_to,
            )
        except LangfuseError:
            details = []
        else:
            details = _overlay_local(db, details)
            details = [
                item
                for item in details
                if _matches_request(item, customer=customer, agent=agent, skill=skill, tool=tool)
            ]
            return [TraceListItem(**detail.model_dump(exclude={"runs"})) for detail in details]
    traces = (
        _filtered_traces(
            db,
            user,
            project_id=project_id,
            model=model,
            status=status,
            started_from=started_from,
            started_to=started_to,
            customer=customer,
            agent=agent,
            skill=skill,
            tool=tool,
        )
        .order_by(LlmObsTrace.started_at.desc(), LlmObsTrace.id.desc())
        .limit(200)
        .all()
    )
    return _trace_items(db, traces)


def summarize(
    db: Session,
    user: CurrentUser,
    *,
    project_id: int | None,
    model: str | None,
    status: str | None,
    started_from: datetime | None,
    started_to: datetime | None,
    customer: str | None = None,
    agent: str | None = None,
    skill: str | None = None,
    tool: str | None = None,
) -> SummaryPublic:
    if langfuse_enabled():
        try:
            scoped = _langfuse_details(
                db,
                user,
                project_id=project_id,
                model=None,
                status=None,
                started_from=started_from,
                started_to=started_to,
            )
        except LangfuseError:
            scoped = None
        if scoped is not None:
            scoped = _overlay_local(db, scoped)
            models = sorted({name for item in scoped for name in item.models})
            customers = sorted({item.customer for item in scoped if item.customer})
            agents = sorted({item.agent_name or name for item in scoped for name in [*item.agents, item.agent_name] if name})
            skills = sorted({name for item in scoped for name in item.skills})
            tools = sorted({name for item in scoped for name in item.tools})
            details = scoped
            if model:
                details = [item for item in details if model in item.models]
            if status in {"success", "error"}:
                details = [item for item in details if item.status == status]
            details = [
                item
                for item in details
                if _matches_request(item, customer=customer, agent=agent, skill=skill, tool=tool)
            ]
            return _summary_from_details(
                details,
                models=models,
                customers=customers,
                agents=agents,
                skills=skills,
                tools=tools,
            )
    filtered = _filtered_traces(
        db,
        user,
        project_id=project_id,
        model=model,
        status=status,
        started_from=started_from,
        started_to=started_to,
        customer=customer,
        agent=agent,
        skill=skill,
        tool=tool,
    )
    success_case = case((LlmObsTrace.status == "success", 1), else_=0)
    total, success, avg_latency = filtered.with_entities(
        func.count(LlmObsTrace.id),
        func.coalesce(func.sum(success_case), 0),
        func.avg(LlmObsTrace.latency_ms),
    ).one()
    total_tokens = (
        db.query(func.coalesce(func.sum(LlmObsRun.total_tokens), 0))
        .filter(LlmObsRun.run_type == "llm", LlmObsRun.trace_id.in_(filtered.with_entities(LlmObsTrace.id)))
        .scalar()
    )
    return SummaryPublic(
        total=int(total or 0),
        success=int(success or 0),
        error=int(total or 0) - int(success or 0),
        avg_latency_ms=int(avg_latency) if avg_latency is not None else None,
        total_tokens=int(total_tokens or 0),
        models=model_options(db, user, project_id),
        **request_options(db, user, project_id),
    )


def get_trace(db: Session, user: CurrentUser, trace_id: int | str) -> TraceDetail | None:
    if langfuse_enabled():
        try:
            found = _langfuse_details(
                db,
                user,
                project_id=None,
                model=None,
                status=None,
                started_from=None,
                started_to=None,
                trace_key=str(trace_id),
            )
        except LangfuseError:
            found = []
        else:
            if found:
                return _overlay_local(db, found)[0]
            if not str(trace_id).isdigit():
                return None
    if not str(trace_id).isdigit():
        return None
    trace = (
        db.query(LlmObsTrace)
        .filter(
            LlmObsTrace.id == int(trace_id),
            LlmObsTrace.project_id.in_(_owned_trace_ids(db, user)),
        )
        .first()
    )
    if trace is None:
        return None
    item = _trace_items(db, [trace])[0]
    runs = (
        db.query(LlmObsRun)
        .filter(LlmObsRun.trace_id == trace.id)
        .order_by(LlmObsRun.started_at, LlmObsRun.id)
        .all()
    )
    return TraceDetail(
        **item.model_dump(),
        runs=[
            RunPublic(
                id=run.id,
                external_id=run.external_id,
                parent_id=run.parent_external_id,
                type=run.run_type,
                name=run.name,
                model=run.model_name,
                system_prompt=run.system_prompt,
                input=run.input_text,
                output=run.output_text,
                status=run.status,
                error=run.error_message,
                started_at=run.started_at,
                finished_at=run.finished_at,
                latency_ms=run.latency_ms,
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                total_tokens=run.total_tokens,
                tool_source=run.tool_source or "",
                connector=run.connector or "",
            )
            for run in runs
        ],
    )
