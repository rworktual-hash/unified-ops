# BackupVault metrics (read-only SSH)

Unified Ops collects BackupVault metrics during the normal fleet collect. It never
starts/stops replication, changes databases, restarts services, deletes backups, or
writes to a remote host.

## Inventory

- Four MySQL/MariaDB replica hosts
- One PostgreSQL replica host
- Six BackupVault application hosts

Canonical hosts and SSH ports are in `backend/app/seed/full_inventory.py`.

## Guardrails

The collector accepts exact command strings from a fixed `frozenset`. No API or UI
input can become a shell command.

| Role | Read-only metrics |
|------|-------------------|
| All | data-filesystem usage, newest file under `/backup`, `/backups`, `/var/backups`, active backup process count |
| MySQL/MariaDB | service state, `SHOW REPLICA STATUS` / legacy `SHOW SLAVE STATUS`, connections, slow-query counter, uptime |
| PostgreSQL | service state, recovery state, replay lag, connection count |
| Application | Docker/Nginx/Cron state, running container names/status |

Explicitly absent: replication start/stop/reset/promote, SQL writes, dump creation,
service restart, container exec/restart, backup deletion, and arbitrary commands.

Some database status fields may show **Unavailable** if root cannot use the local
database socket. This is not reported as unhealthy.

## Configuration

```text
BACKUPVAULT_SSH_INSIGHTS_ENABLED=true
# Empty or * means all project=backupvault hosts:
BACKUPVAULT_SSH_INSIGHTS_IPS=
BACKUPVAULT_SSH_COMMAND_TIMEOUT=30
```

For a pilot, set a comma-separated IP list, restart the API/Celery worker, and run
Collect metrics on those servers. Remove the list after validation to cover all 11.

## API and UI

- `GET /api/backupvault/ssh-overview`
- Sidebar: **BackupVault**
- Storage warning: data filesystem >= 85%
- Stale backup: newest file found in common backup paths is older than 24 hours
- PostgreSQL healthy standby: in recovery and replay lag <= 300 seconds

The backup-path check is intentionally generic. If BackupVault stores artifacts
elsewhere, add the confirmed path as a fixed command in the collector; do not accept
paths from request parameters.
