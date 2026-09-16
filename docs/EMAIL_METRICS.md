# Email metrics (SSH + optional email-management DB)

**Status:** **SSH insights (Option 3)** are on by default for `project=email` — queue, Postfix/Dovecot/OpenDKIM, `pflogsumm` today stats, log sample. No MariaDB required. **DB sync** is optional for full log history like email-management.

Unified Ops combines:

1. **SSH** (from nlp-sm) — host CPU/RAM/disk + **email_ssh_snapshots**: `mailq`, service status, **`pflogsumm -d today`**, recent postfix/mail.log lines. Enabled when `EMAIL_SSH_INSIGHTS_ENABLED=true` (default). Limit hosts with `EMAIL_SSH_INSIGHTS_IPS=82.113.72.84,...` or empty = all email inventory rows.
2. **Read-only MariaDB** — sync parsed mail log rows from **email-management.worktual.tech** into Unified Ops `email_log_events`.

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

Example `.env` on nlp-sm (values from your email-management app config):

```text
EMAIL_MGMT_DATABASE_URL=mysql+pymysql://readonly:SECRET@127.0.0.1:3306/email_management
```

If the DB runs on `82.113.72.84` only, use that IP and ensure nlp-sm can reach it (firewall/VPN).

### Discover schema

```bash
cd /opt/unified-ops && source backend/.venv/bin/activate
python scripts/inspect-email-mgmt-db.py
```

Set table/column env vars to match (defaults may be wrong until you inspect):

```text
EMAIL_MGMT_EVENTS_TABLE=email_logs
EMAIL_MGMT_COL_ID=id
EMAIL_MGMT_COL_TIME=event_time
EMAIL_MGMT_COL_EVENT=event
EMAIL_MGMT_COL_DIRECTION=direction
EMAIL_MGMT_COL_FROM=from_address
EMAIL_MGMT_COL_TO=to_address
EMAIL_MGMT_COL_SUBJECT=subject
EMAIL_MGMT_COL_STATUS=status
EMAIL_MGMT_COL_DSN=dsn
EMAIL_MGMT_COL_QUEUE_ID=queue_id
# Optional — map rows to inventory server by host/IP column:
# EMAIL_MGMT_COL_HOST=hostname
EMAIL_MGMT_HOST_SERVER_MAP=82.113.72.84:email-mgmt-1,82.113.72.80:email-mgmt-2,10.180.0.84:email-mgmt-private
EMAIL_MGMT_DEFAULT_SERVER_NAME=email-mgmt-1
# Optional — match legacy “App Mail (Transactional)” only (column name from inspect script):
# EMAIL_MGMT_COL_CATEGORY=mail_category
# EMAIL_MGMT_CATEGORY_FILTER=transactional
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
| GET | `/email/ssh-overview` | Latest SSH snapshot per email host + summed today stats |
| GET | `/email/overview` | Totals from synced events (24h default) |
| GET | `/email/events?server_id=&limit=` | Recent log rows |
| GET | `/email/servers/{id}/queue` | Latest SSH mailq snapshot |
| POST | `/email/sync` | Admin — pull from email-mgmt DB |
