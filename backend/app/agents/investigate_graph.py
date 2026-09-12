from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.diagnosis import build_diagnosis
from app.agents.tools.readonly_gpu import tool_check_gpu, tool_check_host_snapshot
from app.models.server import Server
from app.policies.guardrails import PHASE5_DEFAULT_RECOMMENDATION


class InvestigateState(TypedDict):
    server: Server
    alert_type: str | None
    alert_message: str | None
    metrics: dict[str, Any]
    tool_results: dict[str, Any]
    summary: str
    diagnosis: str
    recommendation: str


def _node_run_tools(state: InvestigateState) -> dict[str, Any]:
    server = state["server"]
    results: dict[str, Any] = {
        "check_host_snapshot": tool_check_host_snapshot(server),
    }
    if server.server_type == "gpu":
        results["check_gpu"] = tool_check_gpu(server)
    return {"tool_results": results}


def _node_diagnose(state: InvestigateState) -> dict[str, Any]:
    summary, diagnosis = build_diagnosis(
        alert_type=state.get("alert_type"),
        alert_message=state.get("alert_message"),
        metrics=state.get("metrics") or {},
        tool_results=state.get("tool_results") or {},
    )
    return {
        "summary": summary,
        "diagnosis": diagnosis,
        "recommendation": PHASE5_DEFAULT_RECOMMENDATION,
    }


def build_investigate_graph():
    graph = StateGraph(InvestigateState)
    graph.add_node("run_tools", _node_run_tools)
    graph.add_node("diagnose", _node_diagnose)
    graph.add_edge(START, "run_tools")
    graph.add_edge("run_tools", "diagnose")
    graph.add_edge("diagnose", END)
    return graph.compile()


_investigate_app = None


def run_investigate_graph(state: InvestigateState) -> InvestigateState:
    global _investigate_app
    if _investigate_app is None:
        _investigate_app = build_investigate_graph()
    return _investigate_app.invoke(state)


def tool_trace_json(tool_results: dict[str, Any]) -> str:
    return json.dumps(tool_results, default=str)[:8000]
