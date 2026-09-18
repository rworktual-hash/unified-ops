import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchBackupVaultNfs,
  fetchBackupVaultOverview,
  fetchBackupVaultTargets,
  type BackupVaultNfsServer,
  type BackupVaultOverview,
  type BackupVaultSnapshot,
  type BackupVaultTarget,
} from '../api'
import { BackupVaultRunHistory } from './BackupVaultRunHistory'

type TabId = 'runs' | 'targets' | 'nfs' | 'hosts'

function state(value: boolean | null): string {
  return value == null ? '—' : value ? 'Running' : 'Check failed'
}

function replication(snapshot: BackupVaultSnapshot): string {
  if (snapshot.role === 'mysql') {
    if (snapshot.replication_io_running == null && snapshot.replication_sql_running == null) {
      return 'N/A or primary'
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
  if (snapshot.role === 'mysql' || snapshot.role === 'postgres') {
    const parts: string[] = []
    if (snapshot.db_connections != null) {
      parts.push(`DB OK · ${snapshot.db_connections} conn`)
    }
    if (snapshot.service_active != null) {
      parts.push(`Overall ${state(snapshot.service_active)}`)
    }
    if (snapshot.extra_service_status) parts.push(snapshot.extra_service_status)
    return parts.join(' · ') || '—'
  }
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

function StatusPill({ status }: { status: string | null }) {
  const value = (status || 'unknown').toLowerCase()
  return <span className={`bv-pill bv-pill--${value}`}>{value.toUpperCase()}</span>
}

type Props = {
  isAdmin?: boolean
}

export function BackupVaultPanel({ isAdmin: _isAdmin = false }: Props) {
  const [tab, setTab] = useState<TabId>('runs')
  const [overview, setOverview] = useState<BackupVaultOverview | null>(null)
  const [targets, setTargets] = useState<BackupVaultTarget[]>([])
  const [nfs, setNfs] = useState<BackupVaultNfsServer[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loadingExtra, setLoadingExtra] = useState(false)

  const loadSsh = useCallback(async () => {
    try {
      setOverview(await fetchBackupVaultOverview())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load host snapshots')
    }
  }, [])

  const loadCatalog = useCallback(async () => {
    setLoadingExtra(true)
    try {
      const [t, n] = await Promise.all([fetchBackupVaultTargets(), fetchBackupVaultNfs()])
      if (t.ok) setTargets(t.targets)
      if (n.ok) setNfs(n.servers)
      if (!t.ok && t.reason) setError(t.reason)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load BackupVault catalog')
    } finally {
      setLoadingExtra(false)
    }
  }, [])

  useEffect(() => {
    void loadSsh()
    void loadCatalog()
  }, [loadCatalog, loadSsh])

  const mysqlTargets = useMemo(
    () => targets.filter((t) => (t.db_type || '').toLowerCase().includes('mysql')),
    [targets],
  )
  const pgTargets = useMemo(
    () => targets.filter((t) => (t.db_type || '').toLowerCase().includes('postgres')),
    [targets],
  )
  const otherTargets = useMemo(
    () =>
      targets.filter((t) => {
        const type = (t.db_type || '').toLowerCase()
        return !type.includes('mysql') && !type.includes('postgres')
      }),
    [targets],
  )

  return (
    <div className="bv-page">
      <header className="page-head">
        <div>
          <h1>BackupVault</h1>
          <p>Portal run history, DB targets and NFS — plus host SSH health on its own tab.</p>
        </div>
      </header>

      {error ? <p className="banner error">{error}</p> : null}

      <nav className="bv-tabs" aria-label="BackupVault sections">
        {(
          [
            ['runs', 'Run history'],
            ['targets', `DB servers${targets.length ? ` (${targets.length})` : ''}`],
            ['nfs', `NFS${nfs.length ? ` (${nfs.length})` : ''}`],
            ['hosts', 'Host SSH'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? 'bv-tab active' : 'bv-tab'}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === 'runs' && <BackupVaultRunHistory />}

      {tab === 'targets' && (
        <section className="bv-portal">
          <div className="bv-portal-toolbar">
            <div>
              <h2>DB servers</h2>
              <p className="muted">
                {targets.length} backup targets from the portal — read-only, no Backup / Edit / Remove.
              </p>
            </div>
            <button
              type="button"
              className="btn ghost"
              disabled={loadingExtra}
              onClick={() => void loadCatalog()}
            >
              {loadingExtra ? 'Loading…' : 'Refresh'}
            </button>
          </div>
          {pgTargets.length > 0 && (
            <>
              <h3 className="bv-group-title">PostgreSQL · {pgTargets.length}</h3>
              <div className="bv-card-grid">{pgTargets.map((t) => <TargetCard key={t.id} target={t} />)}</div>
            </>
          )}
          {mysqlTargets.length > 0 && (
            <>
              <h3 className="bv-group-title">MySQL · {mysqlTargets.length}</h3>
              <div className="bv-card-grid">{mysqlTargets.map((t) => <TargetCard key={t.id} target={t} />)}</div>
            </>
          )}
          {otherTargets.length > 0 && (
            <>
              <h3 className="bv-group-title">Other · {otherTargets.length}</h3>
              <div className="bv-card-grid">{otherTargets.map((t) => <TargetCard key={t.id} target={t} />)}</div>
            </>
          )}
          {!targets.length && !loadingExtra ? (
            <p className="muted">No backup targets returned from the portal database.</p>
          ) : null}
        </section>
      )}

      {tab === 'nfs' && (
        <section className="bv-portal">
          <div className="bv-portal-toolbar">
            <div>
              <h2>NFS servers</h2>
              <p className="muted">{nfs.length} storage endpoints from the portal.</p>
            </div>
            <button
              type="button"
              className="btn ghost"
              disabled={loadingExtra}
              onClick={() => void loadCatalog()}
            >
              {loadingExtra ? 'Loading…' : 'Refresh'}
            </button>
          </div>
          <div className="bv-card-grid">
            {nfs.map((server) => (
              <article key={server.id} className="bv-card">
                <div className="bv-card-top">
                  <strong>{server.name}</strong>
                  {server.status ? <StatusPill status={server.status} /> : null}
                </div>
                <p className="muted bv-sub">
                  {server.host ?? '—'}
                  {server.role ? ` · ${server.role}` : ''}
                </p>
                <p className="bv-card-meta">{server.export_path || server.mount_point || '—'}</p>
                <p className="muted bv-sub">
                  {server.disk_used || '—'} used · {server.disk_avail || '—'} free
                  {server.disk_size ? ` · ${server.disk_size} total` : ''}
                </p>
              </article>
            ))}
          </div>
        </section>
      )}

      {tab === 'hosts' && overview && (
        <section className="bv-portal">
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
          </div>
          <p className="muted backupvault-note">{overview.note}</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Server</th>
                  <th>Role / services</th>
                  <th>Replication</th>
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
                        {snapshot ? (
                          <>
                            <strong>{snapshot.role}</strong>
                            <br />
                            <span className="muted">{services(snapshot)}</span>
                          </>
                        ) : (
                          'Run fleet collect'
                        )}
                      </td>
                      <td>{snapshot ? replication(snapshot) : '—'}</td>
                      <td>
                        {snapshot?.data_disk_used_pct != null
                          ? `${snapshot.data_disk_used_pct.toFixed(1)}% · ${snapshot.data_disk_free_gb?.toFixed(1) ?? '—'} GB free`
                          : '—'}
                        {snapshot?.latest_backup_size_bytes != null
                          ? ` · ${formatBytes(snapshot.latest_backup_size_bytes)}`
                          : ''}
                      </td>
                      <td>{snapshot ? new Date(snapshot.collected_at).toLocaleString() : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

function TargetCard({ target }: { target: BackupVaultTarget }) {
  return (
    <article className="bv-card">
      <div className="bv-card-top">
        <strong>{target.name}</strong>
        {target.last_status ? <StatusPill status={target.last_status} /> : null}
      </div>
      <p className="muted bv-sub">
        {target.host ?? '—'}
        {target.port ? `:${target.port}` : ''}
      </p>
      <p className="bv-card-meta">{target.database_name || target.description || '—'}</p>
      {target.last_started_at ? (
        <p className="muted bv-sub">Last run {new Date(target.last_started_at).toLocaleString()}</p>
      ) : (
        <p className="muted bv-sub">No runs yet</p>
      )}
    </article>
  )
}
