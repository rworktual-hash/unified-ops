from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.llm_obs import LlmObsProject, LlmObsRun, LlmObsTrace
from app.services.chat import run_chat, source_answer


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[LlmObsProject.__table__, LlmObsTrace.__table__, LlmObsRun.__table__],
    )
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()


def test_campaign_count_comes_from_the_campaign_log(session, monkeypatch):
    monkeypatch.setattr(
        "app.services.chat.build_ops_context",
        lambda *args, **kwargs: {
            "connected_servers": [{"name": "gpu-1", "disk": 91, "mem": 40, "load": 1}],
            "server_count": 1,
            "email_campaign": {
                "ok": True,
                "period_hours": 24,
                "sent": 9,
                "delivered": 8,
                "bounce": 1,
                "deferred": 0,
                "campaign_queued": 2,
                "recent_messages": [],
            },
        },
    )
    reply, _names = run_chat(session, user_message="today how many campaign mails ran")
    assert "9 messages marked sent" in reply
    assert "disk" not in reply.lower()


def test_disk_question_is_not_answered_from_the_portal(session):
    assert source_answer(session, "what is the disk usage") is None


def test_voicemg_question_reads_the_portal_database(session, monkeypatch):
    monkeypatch.setattr(
        "app.services.voicemg_portal.fetch_voicemg_extras",
        lambda: {
            "ok": True,
            "servers": [
                {"hostname": "vmg-1", "active_calls": 4, "packet_loss_pct": 0.2, "mos": 4.1},
                {"hostname": "vmg-2", "active_calls": 1, "packet_loss_pct": 0, "mos": 4.4},
            ],
        },
    )
    reply, _names = run_chat(session, user_message="how many active calls on voicemg")
    assert "MariaDB 10.180.1.222" in reply
    assert "5 active calls" in reply
    assert "vmg-1" in reply


def test_ai_studio_question_counts_customer_traces(session):
    project = LlmObsProject(
        name="ccaas",
        display_name="CCaaS",
        created_at=datetime.now(timezone.utc),
    )
    session.add(project)
    session.flush()
    trace = LlmObsTrace(
        project_id=project.id,
        external_id="ada-1",
        name="what time is it",
        status="success",
        started_at=datetime.now(timezone.utc),
        customer="Ada",
        customer_role="Type 2",
        agent_name="assistant",
        agent_mode="agent",
        created_at=datetime.now(timezone.utc),
    )
    session.add(trace)
    session.flush()
    session.add(
        LlmObsRun(
            trace_id=trace.id,
            external_id="llm",
            run_type="llm",
            name="reply",
            status="success",
            total_tokens=28,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        LlmObsRun(
            trace_id=trace.id,
            external_id="skill",
            run_type="skill",
            name="timekeeping",
            status="success",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    reply, _names = run_chat(session, user_message="how many tokens did the AI Studio customer use")
    assert "1 requests" in reply
    assert "28 tokens" in reply
    assert "Ada" in reply
    assert "timekeeping" in reply
