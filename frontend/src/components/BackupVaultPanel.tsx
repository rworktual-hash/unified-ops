import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchBackupVaultMonitoring,
  fetchBackupVaultNfs,
  fetchBackupVaultOverview,
  fetchBackupVaultTargets,
  type BackupVaultMonDb,
  type BackupVaultMonitoring,
  type BackupVaultMonNfs,
  type BackupVaultNfsServer,
  type BackupVaultOverview,
  type BackupVaultSnapshot,
  type BackupVaultTarget,
} from '../api'
import { BackupVaultDashboard } from './BackupVaultDashboard'
import { BackupVaultIncremental } from './BackupVaultIncremental'
import { BackupVaultRepositories } from './BackupVaultRepositories'
import { BackupVaultRunHistory } from './BackupVaultRunHistory'

type TabId = 'dashboard' | 'runs' | 'targets' | 'incremental' | 'monitoring' | 'storage' | 'nfs' | 'hosts'

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

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`
}

function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

function StatusPill({ status }: { status: string | null }) {
  const value = (status || 'unknown').toLowerCase()
  return <span className={`bv-pill bv-pill--${value}`}>{value.toUpperCase()}</span>
}

type Props = {
  isAdmin?: boolean
}

export function BackupVaultPanel({ isAdmin: _isAdmin = false }: Props) {
  const [tab, setTab] = useState<TabId>('dashboard')
  const [overview, setOverview] = useState<BackupVaultOverview | null>(null)
  const [targets, setTargets] = useState<BackupVaultTarget[]>([])
  const [nfs, setNfs] = useState<BackupVaultNfsServer[]>([])
  const [monitoring, setMonitoring] = useState<BackupVaultMonitoring | null>(null)
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
      const [t, n, m] = await Promise.all([
        fetchBackupVaultTargets(),
        fetchBackupVaultNfs(),
        fetchBackupVaultMonitoring(),
      ])
      if (t.ok) setTargets(t.targets)
      if (n.ok) setNfs(n.servers)
      setMonitoring(m)
      if (!t.ok && t.reason) setError(t.reason)
      if (m && !m.ok && m.reason) setError(m.reason)
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
          <p>Read-only portal metrics from MariaDB — no restore, query, SFTP, or start backup.</p>
        </div>
      </header>

      {error ? <p className="banner error">{error}</p> : null}

      <nav className="bv-tabs" aria-label="BackupVault sections">
        {(
            [
            ['dashboard', 'Dashboard'],
            ['runs', 'Run history'],
            ['targets', `DB servers${targets.length ? ` (${targets.length})` : ''}`],
            ['incremental', 'Incremental'],
            ['monitoring', 'Monitoring'],
            ['storage', 'Storage'],
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

      {tab === 'dashboard' && <BackupVaultDashboard />}
      {tab === 'runs' && <BackupVaultRunHistory />}
      {tab === 'incremental' && <BackupVaultIncremental />}

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

      {tab === 'monitoring' && (
        <section className="bv-portal">
          <div className="bv-portal-toolbar">
            <div>
              <h2>Server monitoring</h2>
              <p className="muted">
                {monitoring
                  ? `${monitoring.db_count} DB servers · ${monitoring.nfs_count} NFS · latest portal snapshots`
                  : 'Latest CPU / memory / disk from backupvault MariaDB'}
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
          <h3 className="bv-group-title">DB servers · {monitoring?.db_servers.length ?? 0}</h3>
          <div className="table-wrap bv-runs-table">
            <table>
              <thead>
                <tr>
                  <th>Server</th>
                  <th>Role</th>
                  <th>CPU</th>
                  <th>MEM</th>
                  <th>Disk</th>
                  <th>Load 1m</th>
                  <th>Conn</th>
                  <th>Active Q</th>
                  <th>QPS</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {(monitoring?.db_servers ?? []).map((row: BackupVaultMonDb) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.name}</strong>
                      <div className="muted bv-sub">
                        {row.host ?? '—'}
                        {row.port ? `:${row.port}` : ''}
                      </div>
                    </td>
                    <td>
                      {(row.db_type || '—').toUpperCase()}
                      {row.ha_role ? ` · ${row.ha_role}` : ''}
                    </td>
                    <td>{fmtPct(row.cpu_pct)}</td>
                    <td>{fmtPct(row.mem_pct)}</td>
                    <td>{fmtPct(row.disk_pct)}</td>
                    <td>{fmtNum(row.load_avg_1)}</td>
                    <td>{fmtNum(row.connections, 0)}</td>
                    <td>{fmtNum(row.active_queries, 0)}</td>
                    <td>{fmtNum(row.qps, 1)}</td>
                    <td>{row.snapshot_at ? new Date(row.snapshot_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 className="bv-group-title">NFS servers · {monitoring?.nfs_servers.length ?? 0}</h3>
          <div className="table-wrap bv-runs-table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Host / path</th>
                  <th>Role</th>
                  <th>Used</th>
                  <th>Free</th>
                  <th>Disk %</th>
                  <th>Inodes</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {(monitoring?.nfs_servers ?? []).map((row: BackupVaultMonNfs) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.name}</strong>
                      {row.status ? (
                        <div>
                          <StatusPill status={row.status} />
                        </div>
                      ) : null}
                    </td>
                    <td>
                      {row.host ?? '—'}
                      <div className="muted bv-sub">{row.export_path || row.mount_point || '—'}</div>
                    </td>
                    <td>{row.role ?? '—'}</td>
                    <td>{row.disk_used ?? '—'}</td>
                    <td>{row.disk_avail ?? '—'}</td>
                    <td>{fmtPct(row.disk_pct)}</td>
                    <td>{fmtPct(row.inode_pct)}</td>
                    <td>{row.snapshot_at ? new Date(row.snapshot_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === 'storage' && (
        <section className="bv-portal">
          <div className="bv-portal-toolbar">
            <div>
              <h2>Storage tiers</h2>
              <p className="muted">NFS pool size from portal `nfs_servers` (Primary / Secondary style tiles).</p>
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
          <div className="bv-card-grid bv-storage-grid">
            {(monitoring?.storage ?? []).map((tile) => (
              <article key={tile.id} className="bv-card bv-storage-card">
                <div className="bv-card-top">
                  <strong>{tile.name}</strong>
                  {tile.role ? <span className="bv-pill bv-pill--unknown">{tile.role}</span> : null}
                </div>
                <p className="muted bv-sub">
                  {tile.host ?? '—'}
                  {tile.path ? ` · ${tile.path}` : ''}
                </p>
                <div className="stat-row backupvault-stat-row">
                  <div className="stat-card">
                    <span className="stat-label">Pool size</span>
                    <span className="stat-value">{tile.disk_size ?? '—'}</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Used</span>
                    <span className="stat-value">{tile.disk_used ?? '—'}</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Free</span>
                    <span className="stat-value">{tile.disk_avail ?? '—'}</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Used %</span>
                    <span className="stat-value">{fmtPct(tile.disk_pct)}</span>
                  </div>
                </div>
                {tile.disk_pct != null ? (
                  <div className="bv-bar" aria-hidden>
                    <div className="bv-bar-fill" style={{ width: `${Math.min(100, tile.disk_pct)}%` }} />
                  </div>
                ) : null}
              </article>
            ))}
          </div>
          {!monitoring?.storage.length && !loadingExtra ? (
            <p className="muted">No NFS storage rows in the portal database.</p>
          ) : null}
          <BackupVaultRepositories />
        </section>
      )}

      {tab === 'nfs' && (
        <NfsCards
          nfs={nfs}
          monitoring={monitoring}
          loading={loadingExtra}
          onRefresh={() => void loadCatalog()}
        />
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

function NfsCards({
  nfs,
  monitoring,
  loading,
  onRefresh,
}: {
  nfs: BackupVaultNfsServer[]
  monitoring: BackupVaultMonitoring | null
  loading: boolean
  onRefresh: () => void
}) {
  const rows = monitoring?.nfs_servers?.length
    ? monitoring.nfs_servers.map((row) => ({
        id: row.id,
        name: row.name,
        host: row.host,
        path: row.export_path || row.mount_point,
        role: row.role,
        status: row.status,
        disk_size: row.disk_size,
        disk_used: row.disk_used,
        disk_avail: row.disk_avail,
        disk_pct: row.disk_pct,
        inode_pct: row.inode_pct,
        snapshot_at: row.snapshot_at,
      }))
    : nfs.map((row) => ({
        id: row.id,
        name: row.name,
        host: row.host,
        path: row.export_path || row.mount_point,
        role: row.role,
        status: row.status,
        disk_size: row.disk_size,
        disk_used: row.disk_used,
        disk_avail: row.disk_avail,
        disk_pct: null as number | null,
        inode_pct: null as number | null,
        snapshot_at: null as string | null,
      }))
  const online = rows.filter((row) => (row.status || '').toLowerCase().includes('online') || row.status == null).length
  const warn = rows.filter((row) => (row.disk_pct ?? 0) >= 85 || (row.inode_pct ?? 0) >= 85).length
  const offline = rows.filter((row) => (row.status || '').toLowerCase().includes('off')).length

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>NFS servers</h2>
          <p className="muted">{rows.length} storage endpoints from the portal — view only.</p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Total NFS</span>
          <span className="stat-value">{rows.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Online</span>
          <span className="stat-value accent">{online}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Warning / critical</span>
          <span className="stat-value warn">{warn}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Offline</span>
          <span className="stat-value warn">{offline}</span>
        </div>
      </div>
      <div className="bv-card-grid bv-storage-grid">
        {rows.map((server) => {
          const pct = server.disk_pct
          const tone = pct == null ? '' : pct >= 90 ? ' crit' : pct >= 85 ? ' warn' : ''
          return (
            <article key={server.id} className="bv-card bv-storage-card">
              <div className="bv-card-top">
                <strong>{server.name}</strong>
                {server.status ? <StatusPill status={server.status} /> : null}
              </div>
              <p className="muted bv-sub">
                {server.host ?? '—'}
                {server.role ? ` · ${server.role}` : ''}
              </p>
              <p className="bv-card-meta">{server.path || '—'}</p>
              <p className="muted bv-sub">
                {server.disk_used || '—'} used · {server.disk_avail || '—'} free
                {server.disk_size ? ` · ${server.disk_size} total` : ''}
                {server.inode_pct != null ? ` · inodes ${fmtPct(server.inode_pct)}` : ''}
              </p>
              {pct != null ? (
                <div className="bv-bar" aria-hidden>
                  <div className={`bv-bar-fill${tone}`} style={{ width: `${Math.min(100, pct)}%` }} />
                </div>
              ) : null}
              <p className="muted bv-sub">
                {pct != null ? `${fmtPct(pct)} used` : 'Usage —'}
                {server.snapshot_at ? ` · checked ${new Date(server.snapshot_at).toLocaleString()}` : ''}
              </p>
            </article>
          )
        })}
      </div>
    </section>
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
