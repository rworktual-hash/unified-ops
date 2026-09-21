# Email metrics (live Campaign extras + SSH + optional sync)

**Status:** **Live Campaign extras** read `worktual_email_campaign` on campaign-db **`10.180.0.203`**. **SSH insights** stay on the mail gateways (84 / 80 / 0.84). Optional **DB sync** copies log rows into Unified Ops.

Unified Ops combines:

1. **Live Campaign extras** (`GET /email/extras`) — read-only SELECT from `.203`:
   - `mail_status` — sent / bounce / deferred / host_not_reachable
   - `postfix_queue_snapshot` — queued / deferred / active / incoming per `server`
   - `email_log_realtime` — last 80 live log rows + 24h/7d/30d counts
   - optional counts from `email_quarantine` and `email_campaign_queue`
   Poll ~5s in the UI; API cache 2s. Never selects password / secret / token / hash columns.
2. **SSH** (from nlp-sm) — host CPU/RAM/disk + **email_ssh_snapshots** (strict allowlist, read-only):

   | Category | What we collect |
   |----------|-----------------|
   | Queue | `mailq`; active/deferred/hold file counts under `/var/spool/postfix/` |
   | Services | `systemctl is-active` postfix, dovecot, opendkim, amavis, clamav |
   | Today totals | `pflogsumm -d today` (received, delivered, bounced, rejected, deferred) |
   | Log hints (today) | `journalctl -u postfix` line counts: reject, bounce, amavis, spam |
   | Firewall | `fail2ban-client status` → currently banned count |
   | Sample | last 30 postfix log lines |

   **Not collected via SSH:** Campaign totals / live logs / quarantine counts (those come from `.203` extras).

   Enabled when `EMAIL_SSH_INSIGHTS_ENABLED=true` (default). Limit with `EMAIL_SSH_INSIGHTS_IPS` or empty = all `project=email` hosts.
3. **Read-only MariaDB sync** (optional) — copy `email_log_realtime` into Unified Ops `email_log_events`.

### Guardrails (mandatory)

| Action | Allowed? |
|--------|----------|
| `SELECT` on email-mgmt events table | Yes (read-only DB user) |
| `INSERT` into nlp-sm `email_log_events` | Yes (local copy only) |
| Send mail / `postsuper` / queue delete / `systemctl restart postfix` via Unified Ops | **No** |
| Remote DB `UPDATE` / `DELETE` | **No** |

Create a MariaDB user with **`SELECT` only** on the events table (and `SHOW`/`information_schema` for inspect script).

## Inventory (SSH targets)

| server_name           | ip_address    | ssh_port |
|-----------------------|---------------|----------|
| email-mgmt-1          | 82.113.72.84  | 4204     |
| email-mgmt-2          | 82.113.72.80  | 4204     |
| email-mgmt-private    | 10.180.0.84   | 4204     |

SSH uses the same keys as other hosts from nlp-sm. **Collect metrics** on an email server stores queue snapshots in `email_queue_snapshots`.

## Email-management database (not SSH)

You need a **MariaDB connection URL** (host, port, database name, read-only user/password) — not the mail server SSH port.

Example `.env` on nlp-sm (read-only user from nlp-sm only):

```text
EMAIL_MGMT_DATABASE_URL=mysql+pymysql://unified_ops_ro:SECRET@10.180.0.203:3306/worktual_email_campaign
```

`@` in a password must be `%40`. Do not commit the password.

### Discover schema

```bash
cd /opt/unified-ops && source backend/.venv/bin/activate
python scripts/inspect-email-mgmt-db.py
```

Set table/column env vars to match (defaults may be wrong until you inspect):

```text
EMAIL_MGMT_EVENTS_TABLE=email_log_realtime
EMAIL_MGMT_COL_ID=id
EMAIL_MGMT_COL_TIME=log_datetime
EMAIL_MGMT_COL_EVENT=event_type
EMAIL_MGMT_COL_DIRECTION=direction
EMAIL_MGMT_COL_FROM=mail_from
EMAIL_MGMT_COL_TO=mail_to
EMAIL_MGMT_COL_SUBJECT=subject
EMAIL_MGMT_COL_STATUS=status
EMAIL_MGMT_COL_DSN=dsn
EMAIL_MGMT_COL_QUEUE_ID=queue_id
EMAIL_MGMT_COL_HOST=server
EMAIL_MGMT_HOST_SERVER_MAP=82.113.72.84:email-mgmt-1,82.113.72.80:email-mgmt-2,10.180.0.84:email-mgmt-private
EMAIL_MGMT_DEFAULT_SERVER_NAME=email-mgmt-1
```

### Sync

- **Admin:** `POST /email/sync` or **Sync mail logs** in the Email UI.
- Cursor stored in `email_sync_state` (incremental by remote `id`).
- **Scheduled (optional):** `EMAIL_MGMT_SCHEDULED_SYNC_ENABLED=true`, `EMAIL_MGMT_SYNC_INTERVAL_SECONDS=120` — Celery beat task `sync_email_events_task` (restart beat after `.env` change).

### Nginx

Add `email` to the API location regex (same as `/auth`, `/servers`):

```nginx
location ~ ^/(health|auth|users|email|servers|...) {
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/email/extras?hours=` | Live Campaign extras from `.203` (24h default) |
| GET | `/email/ssh-overview` | Latest SSH snapshot per email host + summed today stats |
| GET | `/email/overview` | Totals from synced events (24h default) |
| GET | `/email/events?server_id=&limit=` | Recent synced log rows |
| GET | `/email/servers/{id}/queue` | Latest SSH mailq snapshot |
| POST | `/email/sync` | Admin — pull from email-mgmt DB |
