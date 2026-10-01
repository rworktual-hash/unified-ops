# Self-hosted Langfuse OSS

Langfuse runs from its published Docker images, next to Worktual Observability. The FastAPI process and the host-metrics pages are unchanged. The custom LLM Observability ingest (`POST /api/llm-obs/ingest` and `scripts/send_llm_obs_demo.py`) stays until a Langfuse trace is confirmed.

Langfuse OSS is MIT. Do not set `LANGFUSE_EE_LICENSE_KEY` or the Enterprise logo variables. The Langfuse UI keeps the Langfuse name and logo. Worktual hosts it at `https://langfuse.worktual.tech`.

## Start

On the server, from the repo:

```bash
cd /opt/unified-ops/deploy/langfuse
cp .env.example .env
# replace every CHANGEME. ENCRYPTION_KEY must be 64 hex characters: openssl rand -hex 32
docker compose --env-file .env up -d
```

Nginx then proxies `https://langfuse.worktual.tech` to `127.0.0.1:3000`. Add the server block in `docs/nginx-unified-ops.conf.example` to the live nginx site and reload nginx. Open the URL, create an account, and create a project named `crm`. Copy the public key and secret key from that project.

## CRM demo trace

```bash
pip install langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-... \
LANGFUSE_SECRET_KEY=sk-lf-... \
LANGFUSE_BASE_URL=https://langfuse.worktual.tech \
python /opt/unified-ops/scripts/send_langfuse_crm_demo.py
```

In Langfuse, open the trace **CRM chat — find contact and open ticket**. It contains:

- agent `crm-support-agent`
- generation `plan` on `worktual-gemma`, with the system prompt, the user text, the reply, and token counts
- tool `lookup_contact` with a successful output
- tool `create_ticket` with the timeout error
- the agent error and final reply

## CRM, CCaaS, and Ticketing

Each app gets its own Langfuse project and keys. The app does not need LangChain.

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://langfuse.worktual.tech
```

Python:

```python
from langfuse import get_client

langfuse = get_client()
with langfuse.start_as_current_observation(as_type="agent", name="crm-support-agent", input=user_text) as agent:
    with langfuse.start_as_current_observation(as_type="generation", name="plan", model="worktual-gemma", input=messages) as generation:
        generation.update(output=reply, usage_details={"input_tokens": 40, "output_tokens": 18})
    with langfuse.start_as_current_observation(as_type="tool", name="lookup_contact", input=args) as tool:
        tool.update(output=result)
    agent.update(output=final_text)
langfuse.flush()
```

JavaScript (`npm install @langfuse/tracing`):

```ts
import { startActiveObservation } from "@langfuse/tracing";

await startActiveObservation("crm-support-agent", async (agent) => {
  agent.update({ input: userText });
  await startActiveObservation("plan", async (generation) => {
    generation.update({ output: reply, metadata: { model: "worktual-gemma" } });
  }, { asType: "generation" });
  await startActiveObservation("lookup_contact", async (tool) => {
    tool.update({ input: args, output: result });
  }, { asType: "tool" });
  agent.update({ output: finalText });
}, { asType: "agent" });
```

Use the same pattern in CCaaS and Ticketing. Change the agent name and the tool names. Point `LANGFUSE_BASE_URL` at the same host and use that app's own keys.
