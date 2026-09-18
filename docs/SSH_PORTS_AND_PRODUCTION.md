# SSH ports, auth, and production (nlp-sm)

Unified Ops runs on **nlp-sm** and opens SSH **from that host** to each inventory row (`ip_address` + `ssh_port`). Manual SSH from your laptop can succeed while the dashboard fails if nlp-sm uses a different path, port, or key.

**Production UI:** https://observability.worktual.tech  
**App path on server:** `/opt/unified-ops`  
**Repo:** `https://github.com/rworktual-hash/unified-ops.git` (branch `main`)

Inventory source of truth in code: `backend/app/seed/full_inventory.py` (~64 hosts: AI Insights 45 + backupvault/email extras).

---

## SSH ports: 22 vs 4204

Many Worktual hosts expose SSH on **4204**, not **22**. Always verify from nlp-sm:

```bash
ssh -p 22 -o ConnectTimeout=5 root@TARGET_IP
ssh -p 4204 -o ConnectTimeout=5 root@TARGET_IP
```

| Symptom | Meaning |
|---------|---------|
| `Connection refused` on one port | SSH listens on the **other** port (or not at all on that IP). |
| `timed out` | Firewall/routing — not fixed by port alone. |
| `Authentication failed` / password prompt | Reachable; fix **key** on server or set **`ssh_password`** in DB. |

### Current seed defaults (after prod validation)

**Port 4204**

- **GPU:** 165, 166, 148, 149 (users `krishna` / `linuxteam`)
- **Infrastructure (public):** `82.113.72.52` (server-management), all DevOps-Nginx `82.113.92.115–119`, Kong `82.113.92.106`, `82.113.92.111`
- **AI Insights monitoring (internal):** `10.180.1.222` — same server-management box, SSH **4204** (MySQL for legacy portal metrics is a **separate** port, usually **3306** — see `docs/LEGACY_METRICS.md`)
- **Email (public):** `82.113.72.84`, `82.113.72.80`; **email-mgmt-private** `10.180.0.84`
- **VoiceMG:** STT/VMG hosts on `10.180.0.93/95/83/97/98`, `10.180.1.230` (see inventory)
- **BackupVault:** **backupvault-150** only (`10.180.0.150`) among backupvault app/db slaves

**Port 22**

- **Infrastructure:** Grafana `82.113.72.19`, DBs `10.180.0.201–203`
- **VoiceMG:** `10.180.0.76`, `10.180.0.77`, `10.180.0.87`
- **BackupVault / mysql slaves:** `10.180.0.119`, `211`, `212`, `213`, `215`, `90`, `130`, `250`, `85`, `124` (not 150)

Per-host exceptions are normal. Update `full_inventory.py`, then sync DB (below).

---

## SSH authentication

| Mode | Use |
|------|-----|
| `key` | Private key at `CREDENTIAL_GPU_KEY_1_PATH` (prod: `/root/.ssh/id_rsa`). |
| `password` | `ssh_password` column in MariaDB (never returned by API). |
| `auto` | Try key, then password (GPU 165/166, some `root` hosts). |

**GPU 165/166:** user `krishna`, port **4204**, inactive until password is set:

```bash
export SSH_GPU_PASSWORD='...'   # on nlp-sm only, not in Git
python scripts/set-gpu-ssh-password.py
unset SSH_GPU_PASSWORD
```

Or `PATCH /servers/{id}` with `ssh_password` (165/166 auto-activate when password is set).

---

## Production `.env` (nlp-sm)

Typical values (secrets stay on server):

```text
DATABASE_URL=mysql+pymysql://unified_ops:...@127.0.0.1:3306/unified_ops
CREDENTIAL_GPU_KEY_1_PATH=/root/.ssh/id_rsa
SSH_STRICT_HOST_KEYS=false
CORS_ORIGINS=https://observability.worktual.tech
AUTH_ENABLED=true
JWT_SECRET=<long-random-string>
```

**First admin login** (on nlp-sm, never commit the password):

```bash
cd /opt/unified-ops
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
ADMIN_EMAIL='your@gmail.com' ADMIN_PASSWORD='your-secure-password' python scripts/create-admin-user.py
```

The script creates the `app_users` table if needed (no need to start the API first).

Sign in at the UI, open **Users**, and add each teammate’s Gmail + password. Only accounts you create can use the dashboard.

Local dev without login: `AUTH_ENABLED=false` in `.env`.

---

## Deploy workflow

**1. Local:** commit and push to `main`.

**2. On nlp-sm:**

```bash
cd /opt/unified-ops
git pull origin main
source backend/.venv/bin/activate

# After schema or inventory changes:
python scripts/migrate-server-ssh-auth.py    # safe to re-run
python scripts/seed-all-servers.py           # upsert by IP
python scripts/apply-ssh-port-4204.py        # sync ssh_port from inventory

cd frontend && npm run build

# Restart API (example)
pkill -f "uvicorn app.main:app" || true
cd /opt/unified-ops/backend
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> /var/log/unified-ops-api.log 2>&1 &
curl -s http://127.0.0.1:8000/health
```

**Collect metrics for every active server** (SSH — no email-management DB):

```bash
source backend/.venv/bin/activate
python scripts/collect-all-metrics.py
```

Or in the UI: **Servers → Collect all servers** (admin). Optional: run Celery worker + beat for automatic collection every 5 minutes (`METRICS_COLLECT_INTERVAL_SECONDS`).

Nginx serves `frontend/dist` and proxies API. Reference vhost (includes **`auth`** and **`users`** for login): [`nginx-unified-ops.conf.example`](./nginx-unified-ops.conf.example).

On the server after `git pull`, install nginx from the repo (includes `auth`, `users`, `email`, `fleet`, and `/servers/` proxy):

```bash
cd /opt/unified-ops
sudo bash scripts/apply-nginx-unified-ops.sh
```

Source file: [`deploy/nginx/unified-ops.conf`](../deploy/nginx/unified-ops.conf). Example/docs: [`nginx-unified-ops.conf.example`](./nginx-unified-ops.conf.example).

The SPA calls the backend under **`/api/`** (e.g. `/api/health`, `/api/servers`) so nginx never treats API paths as static files. Nginx needs `location ^~ /api/ { proxy_pass ... }` — see [`deploy/nginx/unified-ops.conf`](../deploy/nginx/unified-ops.conf).

If `/api/auth/login` is missing, sign-in fails even when the admin user exists.

**Check from nlp-sm:**

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}'
# via nginx (should return access_token JSON, not HTML):
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://observability.worktual.tech/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}'
```

Restart API after admin script if the shell reported uvicorn **Terminated**:

```bash
pkill -f "uvicorn app.main:app" || true
cd /opt/unified-ops/backend && source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> /var/log/unified-ops-api.log 2>&1 &
```

---

## Scripts reference

| Script | Purpose |
|--------|---------|
| `seed-all-servers.py` | Upsert full inventory from `full_inventory.py` |
| `apply-ssh-port-4204.py` | Sync `ssh_port` (22 or 4204) from inventory into MariaDB |
| `migrate-server-ssh-auth.py` | Add `ssh_password`, `ssh_auth_mode` columns |
| `sync-ai-gpu-ssh-access.py` | GPU usernames, auth mode, active flags |
| `set-gpu-ssh-password.py` | 165/166 password from `SSH_GPU_PASSWORD` env |
| `seed-ai-gpu-servers.py` | Legacy 4-GPU seed only |

---

## UI behaviour

- Lists all **`is_active`** servers as metric cards; inactive hosts appear under **Pending SSH access**.
- Nav copy is still GPU-oriented; inventory includes infra, email, backupvault, VoiceMG.
- Host metrics (RAM, disk, load) work for any reachable Linux SSH host; GPU tiles only when `server_type` is `gpu` and `nvidia-smi` succeeds.
- **GPU product + AI insights (pilot):** read-only SSH for IPs in `GPU_PRODUCT_COLLECT_IPS` (default **81.17.61.148**). Tables: `gpu_product_snapshots`, `gpu_insights_snapshots`; extended `gpu_metrics` (power, clock). After pull run `python scripts/migrate-gpu-ai-insights.py` and restart uvicorn. Set `*` for all GPU hosts after pilot.

---

## Related docs

- [`README.md`](../README.md) — local dev and phases  
- [`Unified_Ops_Full_KT_and_Project_Start_Guide.docx`](../Unified_Ops_Full_KT_and_Project_Start_Guide.docx) — KT (no secrets in repo)
