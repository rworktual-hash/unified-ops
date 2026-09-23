from app.services.alert_suggestion import (
    fallback_suggestion,
    parse_suggestion,
    snap_team,
    suggest_from_text,
    team_for_host,
)


def test_team_for_host_uses_project():
    assert team_for_host("email", "host") == "Email"
    assert team_for_host("voicemg", None) == "VoiceMG"
    assert team_for_host(None, "gpu") == "AI platform"
    assert team_for_host("unknown", "host") == "Ops"


def test_snap_team_keeps_known_name():
    assert snap_team("Infrastructure", "Ops") == "Infrastructure"
    assert snap_team("the voice team", "Ops") == "Voice"
    assert snap_team("Random Dept", "Email") == "Email"


def test_parse_suggestion_reads_fenced_json():
    text = """```json
    {"why": "Disk is full.", "solution": "Recollect and check logs.", "team": "Infrastructure", "time_estimate": "20–40 minutes"}
    ```"""
    parsed = parse_suggestion(text)
    assert parsed is not None
    assert parsed["why"] == "Disk is full."
    assert parsed["time_estimate"] == "20–40 minutes"


def test_suggest_from_text_falls_back_when_json_missing():
    alert = {"title": "High disk", "message": "root is 94%"}
    facts = {"team_hint": "Infrastructure"}
    out = suggest_from_text("not json", alert, facts)
    assert out["from_model"] is False
    assert out["team"] == "Infrastructure"
    assert "94%" in out["why"]


def test_model_team_is_snapped_to_the_host():
    alert = {"title": "nginx down", "message": "nginx is inactive"}
    facts = {"team_hint": "Infrastructure"}
    text = '{"why": "nginx is not running.", "solution": "Request a nginx restart in Approvals.", "team": "Site reliability", "time_estimate": "10–20 minutes"}'
    out = suggest_from_text(text, alert, facts)
    assert out["from_model"] is True
    assert out["team"] == "Infrastructure"
    assert out["solution"].startswith("Request a nginx")


def test_fallback_does_not_invent_a_command():
    out = fallback_suggestion({"title": "CPU", "message": "cpu 99"}, {"team_hint": "AI platform"})
    assert "reboot" not in out["solution"].lower()
    assert out["team"] == "AI platform"
