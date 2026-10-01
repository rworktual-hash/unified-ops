# Langfuse behind Worktual LLM Observability

Langfuse OSS is the trace store. CRM, CCaaS, and Ticketing stay on Worktual Observability. They never receive Langfuse keys and they never open the Langfuse UI.

```text
CRM / CCaaS / Ticketing
  WORKTUAL_LLM_OBS_KEY
  WORKTUAL_LLM_OBS_ENDPOINT=https://observability.worktual.tech/api/llm-obs/ingest
        │
Worktual LLM Observability
        │
Langfuse OSS at http://127.0.0.1:3000
```

Do not set `LANGFUSE_EE_LICENSE_KEY` or `LANGFUSE_UI_LOGO_*`. Do not publish Langfuse on a public name. The Compose file keeps Langfuse on `127.0.0.1:3000`.

## Server setup

```bash
cd /opt/unified-ops/deploy/langfuse
cp .env.example .env
# Replace every CHANGEME. ENCRYPTION_KEY must be 64 hex characters: openssl rand -hex 32
docker compose --env-file .env up -d
```

On the server, open `http://127.0.0.1:3000` once, create one organization and one project, and copy that project's keys into the Worktual backend environment:

```bash
LANGFUSE_HOST=http://127.0.0.1:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

Restart the Worktual API after saving those values. Customer projects (crm, ccaas, ticketing) are created in the LLM Observability page. They all share this one Langfuse project. Langfuse separates them with the Worktual project name.

## What an app configures

```bash
WORKTUAL_LLM_OBS_KEY=wllm_...
WORKTUAL_LLM_OBS_ENDPOINT=https://observability.worktual.tech/api/llm-obs/ingest
```

Send the trace JSON to that endpoint with header `X-Api-Key: $WORKTUAL_LLM_OBS_KEY`. The LLM Observability page reads the trace back from Langfuse and shows the agent, LLM call, system prompt, tools, errors, latency, tokens, cost, and session.

```bash
WORKTUAL_LLM_OBS_KEY=wllm_... \
WORKTUAL_LLM_OBS_ENDPOINT=https://observability.worktual.tech \
python /opt/unified-ops/scripts/send_llm_obs_demo.py
```

The Worktual project and key tables remain in MariaDB. Trace rows are still written there until a Langfuse read-back is confirmed on the server. The page uses Langfuse for traces once `LANGFUSE_HOST` and the two server keys are set.
