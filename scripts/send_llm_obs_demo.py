#!/usr/bin/env python3
"""Send one CRM-style chat trace to LLM Observability.

Usage:
  WORKTUAL_LLM_OBS_KEY=wllm_... WORKTUAL_LLM_OBS_ENDPOINT=https://observability.worktual.tech python scripts/send_llm_obs_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.llm_obs_demo import DEMO_TRACE  # noqa: E402


def main() -> int:
    key = os.environ.get("WORKTUAL_LLM_OBS_KEY", os.environ.get("LLM_OBS_API_KEY", "")).strip()
    endpoint = os.environ.get(
        "WORKTUAL_LLM_OBS_ENDPOINT",
        os.environ.get("LLM_OBS_ENDPOINT", "http://127.0.0.1:8000"),
    ).rstrip("/")
    endpoint = endpoint.removesuffix("/api/llm-obs/ingest")
    if not key:
        print("Set WORKTUAL_LLM_OBS_KEY to a project key from LLM Observability.", file=sys.stderr)
        return 1
    url = f"{endpoint}/api/llm-obs/ingest"
    request = urllib.request.Request(
        url,
        data=json.dumps(DEMO_TRACE).encode(),
        headers={"Content-Type": "application/json", "X-Api-Key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
