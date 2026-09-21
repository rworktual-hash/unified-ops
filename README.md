# Unified Ops

Single operations platform to replace separate monitoring apps (AI Insights, VoiceMG, BackupVault, Email Management, Server Inventory) with one dashboard, server inventory, monitoring, alerts, human approvals, and controlled agent actions.

## Where we are (Sept 2026)

Dashboard product work from the old portals is **in place** (live read + UI), including **Email Campaign extras** from campaign-db. **GPU 165/166** stay last. **5-minute Celery fleet collect** is optional — **Collect now / Collect all** is enough for now.

### Two live data paths (both live — not stale)

| Path | What it is | Used for today |
|------|------------|----------------|
| **MariaDB `10.180.1.222`** | Live product metrics the existing apps keep writing (VoiceMG often every second) | Dashboard tiles, VoiceMG history, AI Insights groups/charts, DID/SSL/domains, BackupVault portal views. **Read-only. Never execute on `.222`.** |
| **SSH Collect → nlp-sm `unified_ops`** | Host health we collect ourselves on the inventory hosts | Server cards, Host SSH tables, **Alerts**, **Investigate**, thin **Approvals** |

**“Old portal”** means the existing apps (voicemg.worktual.tech, aiservers, …), **not** dead data.

### Fleet vs `.222` (same company, match by IP)

Inventory seed is **61** hosts (`backend/app/seed/full_inventory.py`); production UI is ~**59** active (**165/166** usually inactive). `.222` is **not** one table of all 59 — it is split by product. Link = **same IP**, then hostname.

| Inventory group | Live on `.222`? | Database |
|-----------------|-----------------|----------|
| AI / GPU (148, 149, 165, 166) | Yes if listed in AI Insights | `ai_insights_platform` |
| Nginx, Kong, Redis, MySQL, Postgres, PBX, SIP, Grafana, … | Yes (AI Insights groups) | `ai_insights_platform` |
| VoiceMG (~9 hosts) | Yes — calls, MOS, RTP, CPU, disk, NIC, UDP, FDs, process | `voicemg` |
| Infra inventory / VMs / DID / SSL / domains | Yes | `server_inventory` |
| BackupVault hosts | Yes (jobs / NFS) | `backupvault` |
| **Email (3 hosts)** | **No** (gateways 84 / 80) | `EMAIL_MGMT_*` → campaign-db **`10.180.0.203`** `worktual_email_campaign` |

### Agents — finished vs next

The **five domain guides** (AI/GPU, VoiceMG, BackupVault, Email, Infrastructure) use the same three levels: **safe automatic** / **human approval** / **admin-only (diagnose + alert)**. Agents are **for those inventory hosts**, not for executing on `.222`.

| Level | Today | Later |
|-------|--------|--------|
| Safe automatic | **Read-only only** — 5‑min Celery collect (CPU/RAM/disk/GPU + Docker/process/logs/listen). **No restart.** Failures log, no recovery. | Allowlisted restarts only if the team later accepts the risk |
| Human approval | Investigate → explain alert/reason/command → Approve → **Confirm run**. Only **recollect** and **SSH verify**. Living doc: [`docs/AI_SERVER_AGENTS.md`](./docs/AI_SERVER_AGENTS.md) | More Level 5 commands only when added to that doc + allowlist |
| Admin / alert only | **Yes** — Collect alerts **and** live `.222` `ai_server_alerts` → IP match → **Investigate** (read-only) | Never reboot / GPU reset / format / unknown scripts |

**Agreed target for agents (not fully built):**

```
Live .222 (metrics + alerts) → Unified Ops reads → match IP to inventory host
  → guardrails (safe | approve | admin-only) → act only on that host (SSH / allowlisted tools)
```

Never write or execute on `.222`. SSH Collect alerts stay as a second input (host RAM/disk/GPU/collect fail).

### Finished on the dashboard

- Live extras: AI Insights + VoiceMG + **Email Campaign** (poll ~5s; API cache 2s)
- VoiceMG history: Live, 5m, 30m, 1h, 2h, 6h, 12h, Today, Yesterday, 2 days, Week, Range… plus utilization charts and click-host series (`?server_id=`)
- AI Insights group cards + fleet/health/resource charts (not the old pies)
- Infrastructure: Dashboard / Baremetal / Proxmox / VMs / **DID / SSL / Domains** (view-only) / Host SSH
- UI: black sidebar, white metric canvas, purple accents
- Phase 5 Investigate + Phase 6 thin approvals + Agent audit log
- Live `.222` AI Insights alerts on **Alerts** → match IP → Investigate on that inventory host (no restart)

### Still to do (agreed order)

1. **GPU 165 / 166** — only when SSH password works. **Do last.**
2. Optional later: systemd for uvicorn; more Level 5 approval tools (never Level 6).

Docs: [`docs/AI_SERVER_AGENTS.md`](./docs/AI_SERVER_AGENTS.md) (AI Level 4/5 living doc), [`docs/LEGACY_METRICS.md`](./docs/LEGACY_METRICS.md), [`docs/VOICEMG_METRICS.md`](./docs/VOICEMG_METRICS.md), five `*_agent_actions_guide.docx` + KT.

**Approach:** Build and validate everything **locally first**, then deploy the same codebase to the dedicated Unified Ops server.

Full knowledge transfer: [`Unified_Ops_Full_KT_and_Project_Start_Guide.docx`](./Unified_Ops_Full_KT_and_Project_Start_Guide.docx) (no secrets in that doc or in this repo).

**Production SSH ports, deploy on nlp-sm, auth (key/password):** [`docs/SSH_PORTS_AND_PRODUCTION.md`](./docs/SSH_PORTS_AND_PRODUCTION.md)

**Email metrics (SSH queue + email-management DB sync):** [`docs/EMAIL_METRICS.md`](./docs/EMAIL_METRICS.md)

**Scheduled fleet collect (Celery Beat):** [`docs/SCHEDULED_COLLECT.md`](./docs/SCHEDULED_COLLECT.md)

**Production API:** UI and authenticated routes use prefix **`/api`** (e.g. `GET /api/servers`, `POST /api/servers/{id}/collect-metrics`). Root `GET /health` remains for simple uptime checks.

## Architecture (simple)

```
React UI  →  FastAPI
               ├─ nlp-sm MariaDB unified_ops  (inventory, SSH metrics, our alerts, approvals, audit)
               ├─ READ live MariaDB 10.180.1.222  (product metrics/alerts — never execute here)
               ├─ READ live MariaDB 10.180.0.203  (Email Campaign — EMAIL_MGMT_*, SELECT only)
               └─ SSH Collect → inventory hosts (~59 active)

Later: .222 alert → IP match → guardrails → action on that inventory host only
Today: SSH Collect alerts + live `.222` alerts → IP match → Investigate / thin Approve
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
- **Agent:** LangGraph investigate + thin approvals now; `.222` alert → IP match → full guardrails later

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

**Current AI/GPU access**

| Host | IP | SSH | Auth | Collect in UI |
|------|-----|-----|------|----------------|
| DR-GPU1-148 / 149 | `81.17.61.148`, `.149` | 4204 | `linuxteam` + **key** | **Yes** — GPU insights pilot (see below) |
| AI-GPU-Server-1 / 2 | `173.234.75.165`, `.166` | 4204 | `krishna` + **`auto`** | **Paused** — `is_active=false` until password works |

Sync GPU rows from seed:

```bash
python scripts/sync-ai-gpu-ssh-access.py
```

### GPU insights pilot (production: 148 + 149)

Read-only SSH collectors (whitelisted commands only) store extra AI-server metrics on nlp-sm MariaDB:

| Layer | Tables / fields | Examples |
|-------|-----------------|----------|
| Host | `server_metrics` | load, RAM, disk |
| GPU | `gpu_metrics` | per-GPU util, VRAM, temp, **power**, **clock** |
| Product | `gpu_product_snapshots` | vLLM jobs, Docker count, driver/model |
| Host insights | `gpu_insights_snapshots` | processes, TCP, listen sockets, CPU util sample, net bytes (**BIGINT**) |

**Who runs product + insights collect:** servers whose IP is listed in `GPU_PRODUCT_COLLECT_IPS` (comma-separated) or `*` for all `server_type=gpu`. Default in code if unset: **`81.17.61.148` only**. Production example:

```bash
# In .env on nlp-sm (restart uvicorn after change)
GPU_PRODUCT_COLLECT_IPS=81.17.61.148,81.17.61.149
```

After schema changes or first deploy of this feature:

```bash
python scripts/migrate-gpu-ai-insights.py   # gpu_metrics columns + gpu_insights_snapshots; idempotent
```

API startup also runs `ensure_gpu_ai_insights_schema()` so new columns/tables are applied on restart.

UI: **Collect metrics** on a pilot GPU host shows per-GPU tiles, **Host & network**, and **Product metrics** blocks.

**Metrics history charts:** **Metrics history** on each server card (`GET /api/servers/{id}/metrics/history?hours=1|6|24`); needs multiple collects (scheduled or manual).

**Legacy portal metrics:** Read-only MySQL sync from **server-management** (`10.180.1.222` — SSH **4204**, MySQL usually **3306**) — see `docs/LEGACY_METRICS.md`, `scripts/discover-legacy-mysql-via-ssh.py`, `scripts/inspect-legacy-metrics-db.py`. Live extras (no new tabs): `GET /api/legacy-metrics/ai-insights/extras` (Servers page groups + fleet/health/resource charts) and `GET /api/legacy-metrics/voicemg/extras`. VoiceMG history (5m–week + custom): `GET /api/legacy-metrics/voicemg/history`.

### AI-GPU 165 / 166 (later — password / sshpass)

These hosts stay **inactive** in the UI until SSH works from nlp-sm. No code change required when ready:

1. From nlp-sm, verify login (team uses password; optional manual test with `sshpass` — never commit passwords):

   ```bash
   sshpass -p '…' ssh -p 4204 -o StrictHostKeyChecking=no krishna@173.234.75.165 'echo ok'
   ```

2. Store password in DB only (nlp-sm, not Git):

   ```bash
   export SSH_GPU_PASSWORD='…'
   python scripts/set-gpu-ssh-password.py
   ```

   Sets `is_active=true`, `ssh_auth_mode=auto`, user `krishna`.

3. Add IPs to `GPU_PRODUCT_COLLECT_IPS` (or use `*`), restart uvicorn, **Test SSH** → **Collect metrics** — same UI as 148/149.

**SSH ports (22 vs 4204):** Varies by host — public Nginx/Kong/email and many GPU/VoiceMG STT boxes use **4204**; internal DBs, Grafana, and most backupvault/mysql slaves use **22**; **backupvault-150** uses **4204**. Canonical list: `backend/app/seed/full_inventory.py` and [`docs/SSH_PORTS_AND_PRODUCTION.md`](./docs/SSH_PORTS_AND_PRODUCTION.md). After editing inventory, sync MariaDB:

```bash
python scripts/apply-ssh-port-4204.py   # syncs 22 or 4204 from seed
# or: python scripts/seed-all-servers.py
```

**Full inventory** (61 seed hosts / ~59 active in production — AI Insights set + backupvault/email extras; upsert by IP):

```bash
python scripts/seed-all-servers.py
```

**SSH auth modes** (`servers.ssh_auth_mode`): `key` | `password` | `auto`. Passwords live in MariaDB only; API exposes `has_ssh_password`, not the value.

New DB columns on an existing server:

```bash
python scripts/migrate-server-ssh-auth.py
python scripts/seed-all-servers.py
```

GPU **165/166** password (nlp-sm only, never Git): `SSH_GPU_PASSWORD='...' python scripts/set-gpu-ssh-password.py`

### Production (nlp-sm)

| Item | Value |
|------|--------|
| URL | https://observability.worktual.tech |
| Path | `/opt/unified-ops` |
| SSH key | `CREDENTIAL_GPU_KEY_1_PATH=/root/.ssh/id_rsa` |
| Host keys | `SSH_STRICT_HOST_KEYS=false` |

Deploy on nlp-sm:

```bash
cd /opt/unified-ops && git pull origin main
git log -1 --oneline   # should match latest commit on GitHub (e.g. Infrastructure panel)

source backend/.venv/bin/activate
pip install -r backend/requirements.txt
python scripts/migrate-gpu-ai-insights.py   # when GPU insights / schema changed
pkill -f "uvicorn app.main:app" || true; sleep 2
cd backend && nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> /var/log/unified-ops-api.log 2>&1 &

# Required for new sidebar tabs (BackupVault, Email, Infrastructure) — pull alone is not enough
cd /opt/unified-ops/frontend && npm ci && npm run build

# Restart Celery if you use scheduled fleet collect
# pkill -f "celery.*app.celery_app" ; ./scripts/run-celery-worker.sh &
```

Then hard-refresh the browser (Ctrl+Shift+R). Open **Infrastructure** in the left sidebar (not only the Infrastructure domain tab on Servers). Inventory tabs (Dashboard / Baremetal / Proxmox / VMs / DID / SSL / Domains) read MariaDB `server_inventory` live; **Host SSH** is unchanged. DID / SSL / Domain tabs are view-only lists (no add / edit / upload). Run **Collect all** once so SSH snapshots appear.

Step-by-step SSH/nginx/auth: [`docs/SSH_PORTS_AND_PRODUCTION.md`](./docs/SSH_PORTS_AND_PRODUCTION.md).

## Status

**Production (observability.worktual.tech):** ~59 active hosts; SSH host metrics + **live `.222` dashboard**; login via `app_users`. GPU insights pilot on **DR-GPU1-148** and **DR-GPU1-149**.

**Next:** **165/166 last** when SSH password works. Level 4 is 5‑min read-only Celery collect (enable on nlp-sm). Restart stay off.

### Phase 3 — Metrics (Redis + Celery)

Requires **Redis** on `REDIS_URL` (default `redis://127.0.0.1:6379/0`). Then two extra terminals:

```bash
chmod +x scripts/run-celery-worker.sh scripts/run-celery-beat.sh
./scripts/run-celery-worker.sh
./scripts/run-celery-beat.sh
```

Manual collect: UI **Collect now** or `POST /servers/{id}/collect-metrics`. History: `GET /servers/{id}/metrics`.

Collectors only run whitelisted read commands (`free`, `df`, `/proc/loadavg`, `nvidia-smi`, and on GPU pilot hosts: `ss`, `ps`, `/proc/stat`, compute-apps query, etc. — see `backend/app/monitoring/`).

### Phase 4 — Alerts

After each collect, rules run (defaults: RAM ≥85%, disk ≥85% warn / ≥92% critical, GPU temp ≥85°C, collect/GPU errors). Tune via `.env` (`ALERT_*`). Manual resolve: `POST /alerts/{id}/resolve` or UI **Resolve**.

### Phase 5 — Agent (investigation only)

- **LangGraph:** `run_tools` → `diagnose` (no executor, no mutating commands).
- **API:** `POST /alerts/{id}/investigate`, `POST /servers/{id}/investigate`, `GET /agent-actions`.
- **UI:** **Investigate** on alerts/servers; results in **Agent audit log**.
- Optional later: set `OPENAI_API_KEY` for LLM-enriched text (not required in Phase 5).

### Phase 6 — Approvals & executor

Allowlisted actions: `recollect_metrics`, `ssh_verify`, `systemctl_restart` (only if service ∈ `ALLOWLIST_RESTART_SERVICES`).

1. **Request recollect** or **Request SSH verify** on a server card or alert → **pending** approval.
2. **Request restart** appears only when `ALLOWLIST_RESTART_SERVICES` is set (hidden if empty).
3. **Approve** runs the executor on the inventory host and logs `execute` in agent audit.
4. **Reject** closes the request without running anything.

Safe automatic stay off. Nothing mutates until you Approve.

API: `GET /approvals/catalog`, `POST /approvals`, `GET /approvals`, `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject`.
