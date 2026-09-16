# Scheduled fleet metrics collect (Celery + Redis)

Unified Ops can collect **all active servers** on a timer (same logic as **Collect all servers** in the UI).

## Components

| Process | Role |
|---------|------|
| **Redis** | Celery broker (`REDIS_URL`) |
| **Celery worker** | Runs `collect_all_active_servers_task` |
| **Celery beat** | Enqueues task every `METRICS_COLLECT_INTERVAL_SECONDS` (default **300**) |
| **FastAPI** | Unchanged; manual collect still works |

## Enable on nlp-sm

**1. `.env`** (same file as `DATABASE_URL`):

```bash
REDIS_URL=redis://127.0.0.1:6379/0
METRICS_SCHEDULED_COLLECT_ENABLED=true
METRICS_COLLECT_INTERVAL_SECONDS=300
```

GPU pilot hosts (148/149) use longer SSH during collect — if a full fleet run exceeds 5 minutes, raise interval to **600** or **900**.

**2. Redis** (if not running):

```bash
redis-cli ping
# or: apt install redis-server && systemctl start redis
```

**3. Start worker + beat** (after API deploy):

```bash
cd /opt/unified-ops
chmod +x scripts/start-scheduled-collect-nlp-sm.sh
./scripts/start-scheduled-collect-nlp-sm.sh
```

Or manually:

```bash
cd /opt/unified-ops/backend && source .venv/bin/activate
nohup celery -A app.celery_app:celery_app worker --loglevel=info >> /var/log/unified-ops-celery-worker.log 2>&1 &
nohup celery -A app.celery_app:celery_app beat --loglevel=info >> /var/log/unified-ops-celery-beat.log 2>&1 &
```

Restart **beat** after changing `METRICS_SCHEDULED_COLLECT_ENABLED` or interval (worker can keep running).

**4. Verify**

- UI **Servers** tab: “Scheduled collect: every 5 min …”
- `GET /api/fleet/collect-status` (authenticated)
- Logs: `tail -f /var/log/unified-ops-celery-worker.log`
- DB: `SELECT id, finished_at, servers_ok, servers_failed, run_trigger FROM fleet_collect_runs ORDER BY id DESC LIMIT 3;`
- One-off migrate (rename legacy `` `trigger` `` column): `python scripts/migrate-fleet-collect-runs.py`

## History for charts

Each scheduled run appends rows to `server_metrics`, `gpu_metrics`, `gpu_insights_snapshots`, etc.

**UI:** On any server card, open **Metrics history** (1h / 6h / 24h). API: `GET /api/servers/{id}/metrics/history?hours=1`.

More data points appear after Celery beat runs or repeated **Collect metrics**.

## Manual / admin

| Action | How |
|--------|-----|
| Sync collect all | UI **Collect all servers** or `POST /api/fleet/collect-metrics` |
| Queue one Celery job | `POST /api/fleet/collect-metrics?background=true` (admin) |

Runs are logged in `fleet_collect_runs` (`run_trigger`: `celery`, `api_sync`).
