# Legacy portal metrics (server-management MySQL)

Unified Ops SSH collect gives **host health** (CPU, RAM, disk). The old web portals (AI Insights, BackupVault, VoiceMG, server inventory) stored **product metrics** in **MySQL/MariaDB on the AI Insights monitoring server** (server-management).

## Access — two different ports

| What | Host | Port | Notes |
|------|------|------|--------|
| **SSH** (shell, discovery) | `10.180.1.222` internal, or `82.113.72.52` public | **4204** | `root` + key or password — **not 4202** |
| **MySQL** (read-only sync) | Same host | Usually **3306** | Confirm with discover script below |

**4202 is not the MariaDB port.** SSH for this box is **4204**. MySQL listens on its own port (default 3306 unless configured otherwise).

**Email** is separate — use `EMAIL_MGMT_DATABASE_URL`, not this DB.

## Setup on nlp-sm

1. **SSH to server-management** (verify from nlp-sm):

```bash
ssh -p 4204 root@10.180.1.222
# or: ssh -p 4204 root@82.113.72.52
```

2. **Discover MySQL port and databases** (read-only):

```bash
cd /opt/unified-ops && source backend/.venv/bin/activate
SERVER_MGMT_SSH_PASSWORD='...' python scripts/discover-legacy-mysql-via-ssh.py
# or after setting ssh_password on server-management row:
python scripts/discover-legacy-mysql-via-ssh.py --from-inventory
```

3. Create a **read-only** MySQL user on that server (SELECT only on portal databases).

4. Add to `/opt/unified-ops/.env` (use **MySQL port** from step 2, typically 3306):

```env
LEGACY_METRICS_DATABASE_URL=mysql+pymysql://readonly:URL_ENCODED_PASSWORD@10.180.1.222:3306/information_schema

# After inspect — one database per stream, e.g.:
# LEGACY_AI_INSIGHTS_DATABASE=ai_insights_platform
# LEGACY_AI_INSIGHTS_SYNC_ENABLED=true
# LEGACY_AI_INSIGHTS_TABLE=ai_server_metrics
# LEGACY_AI_INSIGHTS_COL_ID=id
# LEGACY_AI_INSIGHTS_COL_TIME=timestamp
# LEGACY_AI_INSIGHTS_COL_HOST=server_id
# LEGACY_AI_INSIGHTS_METRIC_COLS=cpu_utilization,memory_utilization,storage_utilization,load_average

# LEGACY_INFRASTRUCTURE_DATABASE=server_inventory
# LEGACY_INFRASTRUCTURE_TABLE=ai_server_metrics_history
# LEGACY_INFRASTRUCTURE_COL_ID=history_id
# (resource_metrics is empty on prod — use ai_server_metrics_history)

# LEGACY_BACKUPVAULT_DATABASE=backupvault
# LEGACY_BACKUPVAULT_SYNC_ENABLED=true
# ... adjust table/columns from inspect output

LEGACY_METRICS_SCHEDULED_SYNC_ENABLED=true
LEGACY_METRICS_SYNC_INTERVAL_SECONDS=300
```

3. Discover schema (from repo root, venv active):

```bash
python scripts/inspect-legacy-metrics-db.py
```

Review `legacy-metrics-discovery.json`, then set `LEGACY_*_TABLE` and `LEGACY_*_COL_*` to match real column names.

4. Restart API (+ Celery worker/beat if scheduled sync enabled).

5. In the UI (admin): open a domain tab → **Legacy portal metrics** → **Sync now**.

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/legacy-metrics/status` | Connection + per-stream sync state |
| GET | `/api/legacy-metrics/overview/{domain}` | Aggregated synced data (`ai_insights`, `backupvault`, `voicemg`, `infrastructure`) |
| GET | `/api/legacy-metrics/points` | Raw synced points |
| POST | `/api/legacy-metrics/sync` | Admin — all enabled streams |
| POST | `/api/legacy-metrics/sync/{domain}` | Admin — one stream |
| GET | `/api/legacy-metrics/discovery` | Admin — live DB/table list |

## Guardrails

- Remote DB: **SELECT only**, incremental by id (same pattern as email log sync).
- No writes, deletes, or arbitrary SQL from config.
- Table and column names must match `[A-Za-z0-9_]+` (validated in queries via backticks).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| SSH failed | Use port **4204**: `ssh -p 4204 root@10.180.1.222` |
| MySQL connection failed | Run discover script; try port **3306** not 4202/4204; firewall from nlp-sm to MySQL port |
| Stream disabled | `LEGACY_*_SYNC_ENABLED=true` and `LEGACY_*_DATABASE` set |
| Table not found | Re-run inspect script; fix `LEGACY_*_TABLE` |
| Empty overview | Run **Sync now**; confirm remote table has rows with `id > last_source_id` |
| Unmapped hosts | Set `LEGACY_METRICS_HOST_SERVER_MAP=10.180.0.90:backupvault-90,...` |
