import { useCallback, useEffect, useState } from 'react'
import {
  fetchBackupVaultOverview,
  type BackupVaultOverview,
  type BackupVaultSnapshot,
} from '../api'

function state(value: boolean | null): string {
  return value == null ? '—' : value ? 'Healthy' : 'Down'
}

function replication(snapshot: BackupVaultSnapshot): string {
  if (snapshot.role === 'mysql') {
    if (snapshot.replication_io_running == null && snapshot.replication_sql_running == null) {
      return 'Unavailable'
    }
    return snapshot.replication_io_running && snapshot.replication_sql_running
      ? `Healthy${snapshot.replication_lag_seconds != null ? ` · ${snapshot.replication_lag_seconds}s` : ''}`
      : `Issue · IO ${state(snapshot.replication_io_running)} · SQL ${state(snapshot.replication_sql_running)}`
  }
  if (snapshot.role === 'postgres') {
    if (snapshot.replica_in_recovery == null) return 'Unavailable'
    return snapshot.replica_in_recovery
      ? `Standby${snapshot.replication_lag_seconds != null ? ` · ${snapshot.replication_lag_seconds}s` : ''}`
      : 'Not in recovery'
  }
  return '—'
}

function services(snapshot: BackupVaultSnapshot): string {
  if (snapshot.role !== 'app') return state(snapshot.service_active)
  const base = [
    snapshot.docker_active == null ? null : `Docker ${state(snapshot.docker_active)}`,
    snapshot.nginx_active == null ? null : `Nginx ${state(snapshot.nginx_active)}`,
    snapshot.cron_active == null ? null : `Cron ${state(snapshot.cron_active)}`,
  ]
    .filter(Boolean)
    .join(' · ')
  return [base, snapshot.extra_service_status].filter(Boolean).join(' · ') || 'Unavailable'
}

function formatBytes(value: number | null): string {
  if (value == null) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let amount = value
  let index = 0
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024
    index += 1
  }
  return `${amount.toFixed(index > 2 ? 2 : 1)} ${units[index]}`
}

export function BackupVaultPanel() {
  const [overview, setOverview] = useState<BackupVaultOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setOverview(await fetchBackupVaultOverview())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load BackupVault metrics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>BackupVault</h1>
          <p>
            Read-only SSH monitoring for database replicas, application services, storage and backup
            recency. No database writes, replication controls or service restarts.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </header>

      {error ? <p className="banner error">{error}</p> : null}

      {overview ? (
        <>
          <section className="panel">
            <div className="stat-row backupvault-stat-row">
              <div className="stat-card">
                <span className="stat-label">Hosts collected</span>
                <span className="stat-value">
                  {overview.collected_hosts}/{overview.total_hosts}
                </span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Replication healthy</span>
                <span className="stat-value accent">{overview.replication_healthy}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Replication issues</span>
                <span className="stat-value warn">{overview.replication_unhealthy}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Storage ≥85%</span>
                <span className="stat-value warn">{overview.storage_warning}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Backups older 24h</span>
                <span className="stat-value warn">{overview.stale_backup_hosts}</span>
              </div>
            </div>
            <p className="muted backupvault-note">{overview.note}</p>
          </section>

          <section className="panel">
            <h2>Latest SSH snapshots</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Server</th>
                    <th>Role / services</th>
                    <th>Replication</th>
                    <th>DB</th>
                    <th>Data storage</th>
                    <th>Latest backup found</th>
                    <th>Collected</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.servers.map((server) => {
                    const snapshot = server.snapshot
                    return (
                      <tr key={server.server_id}>
                        <td>
                          {server.server_name}
                          <br />
                          <span className="muted">{server.ip_address}</span>
                        </td>
                        <td>
                          {snapshot ? (
                            <>
                              <strong>{snapshot.role}</strong>
                              <br />
                              <span className="muted">{services(snapshot)}</span>
                              {snapshot.role === 'app' && snapshot.containers_running != null
                                ? ` · ${snapshot.containers_running} containers`
                                : ''}
                            </>
                          ) : (
                            'Run fleet collect'
                          )}
                        </td>
                        <td>{snapshot ? replication(snapshot) : '—'}</td>
                        <td>
                          {snapshot?.db_connections != null
                            ? `${snapshot.db_connections} connections`
                            : '—'}
                          {snapshot?.slow_queries != null
                            ? ` · ${snapshot.slow_queries} slow`
                            : ''}
                        </td>
                        <td>
                          {snapshot?.data_disk_used_pct != null
                            ? `${snapshot.data_mount ?? 'data'} · ${snapshot.data_disk_used_pct.toFixed(1)}% · ${snapshot.data_disk_free_gb?.toFixed(1) ?? '—'} GB free`
                            : '—'}
                        </td>
                        <td>
                          {snapshot?.latest_backup_at
                            ? new Date(snapshot.latest_backup_at).toLocaleString()
                            : 'Not found in common paths'}
                          {snapshot?.latest_backup_size_bytes != null
                            ? ` · ${formatBytes(snapshot.latest_backup_size_bytes)}`
                            : ''}
                          {snapshot?.backup_file_count != null
                            ? ` · ${snapshot.backup_file_count} files`
                            : ''}
                          {snapshot?.backup_total_size_bytes != null
                            ? ` · total ${formatBytes(snapshot.backup_total_size_bytes)}`
                            : ''}
                        </td>
                        <td>
                          {snapshot ? new Date(snapshot.collected_at).toLocaleString() : '—'}
                          {snapshot?.healthcheck_status ? (
                            <span className="muted">
                              <br />
                              {snapshot.healthcheck_status}
                            </span>
                          ) : null}
                          {snapshot?.collect_error ? (
                            <span className="backupvault-error" title={snapshot.collect_error}>
                              {' '}
                              · partial
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="muted">
              “Unavailable” means the fixed read-only command lacked local socket permission or the
              utility/path is absent; it does not mean replication is unhealthy.
            </p>
          </section>
        </>
      ) : null}
    </>
  )
}
