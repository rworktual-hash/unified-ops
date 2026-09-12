# Unified Ops

Single operations platform to replace separate monitoring apps (AI Insights, VoiceMG, BackupVault, Email Management, Server Inventory) with one dashboard, server inventory, monitoring, alerts, human approvals, and controlled agent actions.

**Approach:** Build and validate everything **locally first**, then deploy the same codebase to the dedicated Unified Ops server.

Full knowledge transfer and inventory details: [`Unified_Ops_Full_KT_and_Project_Start_Guide.docx`](./Unified_Ops_Full_KT_and_Project_Start_Guide.docx) (no secrets in that doc or in this repo).

## Architecture (simple)

```
React UI  →  FastAPI  →  MariaDB (persistent data)
                ↑
Celery Beat → Redis → Celery Workers → SSH / safe checks → target servers

Alerts → LangGraph agent → guardrails → auto action | human approval → executor → verify → audit log
```

| Component | Role |
|-----------|------|
| React | Dashboard: servers, metrics, alerts, approvals |
| FastAPI | REST API for the UI and orchestration |
| MariaDB | Servers, metrics, alerts, approvals, audit history |
| Celery + Redis | Scheduled metric collection and background jobs |
| Workers | Fixed collectors; no free-form decisions |
| Agent + executor | Investigate issues; run **predefined** tools only |

**Principles:** One app (not five). Workers collect; the agent decides within policy. Secrets stay on the backend—never in the frontend or open-ended LLM shell access.

## Tech stack

- **Frontend:** React
- **Backend:** FastAPI (Python)
- **Database:** MariaDB (`unified_ops`)
- **Tasks:** Celery, Redis
- **Agent (later):** LangGraph + domain tools + guardrails

## Local prerequisites

- Python 3.11+
- Node.js (LTS)
- MariaDB (local instance or Docker)
- Redis (local instance or Docker)

Use environment variables for all secrets. Copy from `.env.example` when added—never commit real passwords, SSH private keys, or API tokens.

## Planned repository layout

```
frontend/                 # React UI
backend/
  app/
    main.py               # FastAPI entry
    api/                  # Routes (servers, metrics, alerts, approvals)
    db/                   # MariaDB session / connection
    models/               # SQLAlchemy models
    services/             # Business logic
    monitoring/           # SSH collectors, metric parsing
    tasks/                # Celery tasks
    agents/               # LangGraph workflow (phase 5+)
    policies/             # Guardrails
    executors/            # Controlled remote actions
.env.example
```

## Development order

Do **not** start with the agent. Prove inventory + SSH + metrics first.

1. **Foundation** — FastAPI health, MariaDB, `servers` CRUD, React server list
2. **Connectivity** — `credential_ref`, SSH connection test API + UI
3. **Monitoring** — Celery Beat/Worker, CPU/RAM/disk (then GPU with command timeouts), metrics API + UI
4. **Alerts** — Thresholds and incident list
5. **Agent** — LangGraph, domain tools, safe diagnosis only
6. **Approvals** — Approve/reject, executor, audit logs
7. **Production** — New Unified Ops server: Nginx, HTTPS, managed services, SSH keys on targets, roll out server-by-server

**First milestone:** Add server → save in MariaDB → worker SSH → collect metrics → API → React.

**Second milestone:** GPU/alerts → agent → guardrails → auto or approval → verify → audit.

## Initial API surface (target)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/servers` | Add server |
| GET | `/servers` | List servers |
| GET | `/servers/{id}` | Server detail |
| POST | `/servers/{id}/test-connection` | Safe SSH test |
| GET | `/servers/{id}/metrics` | Recent metrics |
| GET | `/alerts` | List alerts |
| GET | `/approvals` | Pending approvals |
| POST | `/approvals/{id}/approve` | Approve action |
| POST | `/approvals/{id}/reject` | Reject action |
| GET | `/agent-actions` | Audit history |

## MariaDB local vs server

Same engine and migrations locally and in production. Only `DATABASE_URL` (host, user, password) changes between `.env` on your machine and the server. Default MariaDB port: `3306`.

Example (local):

```text
DATABASE_URL=mysql+pymysql://unified_ops:YOUR_DEV_PASSWORD@127.0.0.1:3306/unified_ops
```

## Security

- Prefer SSH keys for target servers; store `credential_ref` in DB, keys in a protected secret store / env.
- Rotate any credentials that were exposed during earlier infrastructure review (see KT appendix).
- Reboot/shutdown, GPU reset, and destructive operations remain **admin manual only**.

## Quick start (Phase 1, local)

**1. MariaDB** (Docker, host port **3307** — avoids clash with other MariaDB on 3306):

```bash
chmod +x scripts/start-mariadb.sh
./scripts/start-mariadb.sh
```

Connection string:

`mysql+pymysql://unified_ops:unified_ops_dev@127.0.0.1:3307/unified_ops`

**`docker-compose up -d` broken?** On Ubuntu, old **docker-compose 1.29** + **urllib3 2.x** often fails with `Not supported URL scheme http+docker`. Use the script above (plain `docker run`) instead. Optional fixes later: install the Compose v2 plugin (`docker compose`) or use Compose from pip in a venv—not required for this project.

Copy env and adjust if needed:

```bash
cp .env.example .env
```

**2. Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**3. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — add servers; data is stored in MariaDB. API docs: http://localhost:8000/docs

**Seed AI/GPU servers** (4 hosts from the AI domain doc; skips duplicates by IP):

```bash
source backend/.venv/bin/activate
python scripts/seed-ai-gpu-servers.py
# optional: SEED_SSH_USERNAME=your-user python scripts/seed-ai-gpu-servers.py
```

Update `ssh_username` in the UI or re-seed after server team confirms the monitor user.

### Phase 2 — SSH key and test connection

1. Generate a key (send **`.pub`** to server team for GPU hosts, port **4204**):

   ```bash
   chmod +x scripts/generate-unified-ops-ssh-key.sh
   ./scripts/generate-unified-ops-ssh-key.sh
   ```

2. Copy `.env.example` → `.env` and set `CREDENTIAL_GPU_KEY_1_PATH` to the **private** key path.

3. Point existing AI rows at the ref (if seeded before Phase 2):

   ```bash
   python scripts/set-ai-gpu-credential-ref.py
   ```

4. Restart backend, open UI, click **Test SSH** per server (or `POST /servers/{id}/test-connection`).

**Current AI/GPU access (local dev):** DR **148/149** use user **`linuxteam`** + `~/.ssh/id_rsa` via `CREDENTIAL_GPU_KEY_1_PATH`. **165/166** stay **inactive** until server team adds the same key. Sync DB:

```bash
python scripts/sync-ai-gpu-ssh-access.py
```

## Status

**Phase 6:** Approval queue + controlled executor (allowlisted actions). **Next:** Production hardening / new server deploy.

### Phase 3 — Metrics (Redis + Celery)

Requires **Redis** on `REDIS_URL` (default `redis://127.0.0.1:6379/0`). Then two extra terminals:

```bash
chmod +x scripts/run-celery-worker.sh scripts/run-celery-beat.sh
./scripts/run-celery-worker.sh
./scripts/run-celery-beat.sh
```

Manual collect: UI **Collect now** or `POST /servers/{id}/collect-metrics`. History: `GET /servers/{id}/metrics`.

Collectors only run whitelisted read commands (`free`, `df`, `/proc/loadavg`, `nvidia-smi` with timeout).

### Phase 4 — Alerts

After each collect, rules run (defaults: RAM ≥85%, disk ≥85% warn / ≥92% critical, GPU temp ≥85°C, collect/GPU errors). Tune via `.env` (`ALERT_*`). Manual resolve: `POST /alerts/{id}/resolve` or UI **Resolve**.

### Phase 5 — Agent (investigation only)

- **LangGraph:** `run_tools` → `diagnose` (no executor, no mutating commands).
- **API:** `POST /alerts/{id}/investigate`, `POST /servers/{id}/investigate`, `GET /agent-actions`.
- **UI:** **Investigate** on alerts/servers; results in **Agent audit log**.
- Optional later: set `OPENAI_API_KEY` for LLM-enriched text (not required in Phase 5).

### Phase 6 — Approvals & executor

Allowlisted actions: `recollect_metrics`, `ssh_verify`, `systemctl_restart` (only if service ∈ `ALLOWLIST_RESTART_SERVICES`).

1. **Request recollect** on an active server → creates **pending** approval.
2. **Approve** runs the executor and logs `execute` in agent audit.
3. **Reject** closes the request without running anything.

API: `POST /approvals`, `GET /approvals`, `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject`.
