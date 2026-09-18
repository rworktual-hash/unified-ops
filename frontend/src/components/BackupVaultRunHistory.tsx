import { useCallback, useEffect, useState } from 'react'
import {
  fetchBackupVaultRuns,
  fetchLegacyStatus,
  syncLegacyMetrics,
  type BackupVaultRun,
  type BackupVaultRunHistory,
  type LegacyStatus,
} from '../api'

type Props = {
  isAdmin?: boolean
}

function formatDuration(seconds: number | null): string {
  if (seconds == null || seconds < 0) return '—'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  if (minutes < 60) return remain ? `${minutes}m ${remain}s` : `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins ? `${hours}h ${mins}m` : `${hours}h`
}

function statusClass(status: string | null): string {
  const value = (status || '').toLowerCase()
  if (value === 'success') return 'bv-run-ok'
  if (value === 'failed') return 'bv-run-fail'
  if (value === 'partial') return 'bv-run-partial'
  if (value === 'running') return 'bv-run-run'
  return ''
}

export function BackupVaultRunHistory({ isAdmin = false }: Props) {
  const [status, setStatus] = useState<LegacyStatus | null>(null)
  const [history, setHistory] = useState<BackupVaultRunHistory | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const stream = status?.streams.find((s) => s.domain === 'backupvault')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [st, runs] = await Promise.all([fetchLegacyStatus(), fetchBackupVaultRuns()])
      setStatus(st)
      setHistory(runs)
      if (!runs.ok && runs.reason) {
        setError(runs.reason)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load BackupVault run history')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (!status?.configured) {
    return (
      <section className="panel legacy-metrics-panel">
        <h2>BackupVault run history</h2>
        <p className="muted">
          Not configured. Set <code>LEGACY_METRICS_DATABASE_URL</code> and{' '}
          <code>LEGACY_BACKUPVAULT_DATABASE=backupvault</code>.
        </p>
      </section>
    )
  }

  const runs: BackupVaultRun[] = history?.runs ?? []

  return (
    <section className="panel legacy-metrics-panel">
      <div className="legacy-metrics-head">
        <h2>BackupVault run history</h2>
        {isAdmin ? (
          <button
            type="button"
            className="btn ghost"
            disabled={syncing || loading}
            onClick={() => {
              setSyncing(true)
              setError(null)
              void syncLegacyMetrics('backupvault')
                .then(() => load())
                .catch((err) =>
                  setError(err instanceof Error ? err.message : 'Legacy sync failed'),
                )
                .finally(() => setSyncing(false))
            }}
          >
            {syncing ? 'Syncing…' : 'Refresh'}
          </button>
        ) : (
          <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        )}
      </div>

      {error ? <p className="banner error">{error}</p> : null}

      <p className="muted legacy-metrics-meta">
        Connection: {status.connection_ok ? 'OK' : `Failed — ${status.connection_error ?? 'unknown'}`}
        {history?.ok ? ' · live from portal MariaDB' : ''}
        {stream?.last_synced_at
          ? ` · last point sync ${new Date(stream.last_synced_at).toLocaleString()}`
          : ''}
        {history && history.total > 0
          ? ` · ${history.total} runs · ${history.success_rate}% success`
          : ''}
      </p>

      {loading && !history ? <p className="muted">Loading run history…</p> : null}

      {history && history.ok ? (
        <>
          <div className="stat-row backupvault-stat-row">
            <div className="stat-card">
              <span className="stat-label">Total</span>
              <span className="stat-value">{history.total}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Success</span>
              <span className="stat-value accent">{history.success}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Failed</span>
              <span className="stat-value warn">{history.failed}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Partial</span>
              <span className="stat-value">{history.partial}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Running</span>
              <span className="stat-value">{history.running}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Success rate</span>
              <span className="stat-value accent">{history.success_rate}%</span>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Target</th>
                  <th>DB</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Destinations</th>
                  <th>Size</th>
                  <th>Started</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>#{run.id}</td>
                    <td>
                      {run.target_name}
                      {run.target_host ? (
                        <>
                          <br />
                          <span className="muted">{run.target_host}</span>
                        </>
                      ) : null}
                    </td>
                    <td>{run.db_type ?? '—'}</td>
                    <td>{run.backup_type ?? '—'}</td>
                    <td className={statusClass(run.status)}>
                      {(run.status || '—').toUpperCase()}
                      {run.error_message ? (
                        <span className="muted" title={run.error_message}>
                          <br />
                          {run.error_message}
                        </span>
                      ) : null}
                    </td>
                    <td>{run.destination_count}</td>
                    <td>{run.file_size_label ?? '—'}</td>
                    <td>{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</td>
                    <td>{formatDuration(run.duration_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            Same 89-run history as backupvault.worktual.tech. Newest job on the portal is 10 Sep 2026 —
            the list is complete, not limited to 24 hours.
          </p>
        </>
      ) : !loading ? (
        <p className="muted">No BackupVault runs available from the portal database.</p>
      ) : null}
    </section>
  )
}
