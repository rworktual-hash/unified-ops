#!/usr/bin/env python3
"""Send one CRM chat turn to self-hosted Langfuse.

The existing Worktual ingest demo (scripts/send_llm_obs_demo.py) is unchanged.

Install once: pip install langfuse

  LANGFUSE_PUBLIC_KEY=pk-lf-... \\
  LANGFUSE_SECRET_KEY=sk-lf-... \\
  LANGFUSE_BASE_URL=https://langfuse.worktual.tech \\
  python scripts/send_langfuse_crm_demo.py
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    missing = [name for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL") if not os.environ.get(name)]
    if missing:
        print("Set " + ", ".join(missing), file=sys.stderr)
        return 1
    try:
        from langfuse import get_client, propagate_attributes
    except ImportError:
        print("pip install langfuse", file=sys.stderr)
        return 1

    system_prompt = "You are the CRM assistant. Use tools. Never invent contact ids."
    user_text = "Find Acme and open a ticket about billing"
    langfuse = get_client()

    with langfuse.start_as_current_observation(
        as_type="agent",
        name="crm-support-agent",
        input=user_text,
    ) as agent:
        with propagate_attributes(trace_name="CRM chat — find contact and open ticket"):
            with langfuse.start_as_current_observation(
                as_type="generation",
                name="plan",
                model="worktual-gemma",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            ) as generation:
                generation.update(
                    output="I will look up the contact, then create a ticket.",
                    usage_details={"input_tokens": 40, "output_tokens": 18, "total_tokens": 58},
                )
            with langfuse.start_as_current_observation(
                as_type="tool",
                name="lookup_contact",
                input={"name": "Acme"},
            ) as tool:
                tool.update(output={"id": "c-19", "name": "Acme"})
            with langfuse.start_as_current_observation(
                as_type="tool",
                name="create_ticket",
                input={"contact_id": "c-19", "subject": "billing"},
            ) as tool:
                tool.update(level="ERROR", status_message="CRM API timeout after 30s")
            agent.update(
                output="Could not open the ticket.",
                level="ERROR",
                status_message="create_ticket failed: CRM API timeout",
            )

    langfuse.flush()
    print("Sent CRM trace to Langfuse. Open the crm project and refresh traces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
