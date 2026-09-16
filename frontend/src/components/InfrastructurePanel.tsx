import { useCallback, useEffect, useState } from 'react'
import {
  fetchInfrastructureOverview,
  type InfrastructureOverview,
  type InfrastructureSnapshot,
} from '../api'

function state(value: boolean | null): string {
  return value == null ? '—' : value ? 'Healthy' : 'Down'
}

function replication(snapshot: InfrastructureSnapshot): string {
  if (snapshot.role === 'mysql') {
    if (snapshot.replication_io_running == null && snapshot.replication_sql_running == null) {
      return 'N/A or primary'
    }
    return snapshot.replication_io_running && snapshot.replication_sql_running
      ? `Replica OK${snapshot.replication_lag_seconds != null ? ` · ${snapshot.replication_lag_seconds}s` : ''}`
      : `Issue · IO ${state(snapshot.replication_io_running)} · SQL ${state(snapshot.replication_sql_running)}`
  }
  if (snapshot.role === 'postgres') {
    if (snapshot.replica_in_recovery == null) return 'Unavailable'
    return snapshot.replica_in_recovery
      ? `Standby${snapshot.replication_lag_seconds != null ? ` · ${snapshot.replication_lag_seconds}s` : ''}`
      : 'Primary'
  }
  return '—'
}

function services(snapshot: InfrastructureSnapshot): string {
  const parts: string[] = []
  if (snapshot.role === 'nginx' || snapshot.role === 'kafka') {
    if (snapshot.nginx_active != null) parts.push(`Nginx ${state(snapshot.nginx_active)}`)
  }
  if (snapshot.role === 'kong' && snapshot.kong_active != null) {
    parts.push(`Kong ${state(snapshot.kong_active)}`)
  }
  if (snapshot.role === 'redis') {
    if (snapshot.redis_role) parts.push(`role ${snapshot.redis_role}`)
    if (snapshot.redis_connected_clients != null) {
      parts.push(`${snapshot.redis_connected_clients} clients`)
    }
  }
  if (snapshot.service_active != null && !parts.length) {
    parts.push(state(snapshot.service_active))
  }
  if (snapshot.docker_active != null) parts.push(`Docker ${state(snapshot.docker_active)}`)
  if (snapshot.extra_service_status) parts.push(snapshot.extra_service_status)
  return parts.join(' · ') || '—'
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

export function InfrastructurePanel() {
  const [overview, setOverview] = useState<InfrastructureOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setOverview(await fetchInfrastructureOverview())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load infrastructure metrics')
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
          <h1>Infrastructure</h1>
          <p>
            Read-only SSH monitoring for Nginx, Kong, databases, Redis, Grafana, PBX/SIP, and
            platform hosts. No restarts, config changes, or control actions.
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
                <span className="stat-label">Primary service down</span>
                <span className="stat-value warn">{overview.service_down}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Storage ≥85%</span>
                <span className="stat-value warn">{overview.storage_warning}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">DB replication OK</span>
                <span className="stat-value accent">{overview.replication_healthy}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">DB replication issues</span>
                <span className="stat-value warn">{overview.replication_unhealthy}</span>
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
                    <th>Type / role</th>
                    <th>Services</th>
                    <th>Replication</th>
                    <th>DB / Redis</th>
                    <th>Storage</th>
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
                          {server.server_type ?? '—'}
                          {snapshot ? (
                            <>
                              <br />
                              <strong>{snapshot.role}</strong>
                            </>
                          ) : null}
                        </td>
                        <td>{snapshot ? services(snapshot) : 'Run fleet collect'}</td>
                        <td>{snapshot ? replication(snapshot) : '—'}</td>
                        <td>
                          {snapshot?.role === 'redis'
                            ? formatBytes(snapshot.redis_used_memory_bytes)
                            : snapshot?.db_connections != null
                              ? `${snapshot.db_connections} conn`
                              : '—'}
                          {snapshot?.slow_queries != null ? ` · ${snapshot.slow_queries} slow` : ''}
                        </td>
                        <td>
                          {snapshot?.data_disk_used_pct != null
                            ? `${snapshot.data_mount ?? '/'} · ${snapshot.data_disk_used_pct.toFixed(1)}% · ${snapshot.data_disk_free_gb?.toFixed(1) ?? '—'} GB free`
                            : '—'}
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
          </section>
        </>
      ) : null}
    </>
  )
}
