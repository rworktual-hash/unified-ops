import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchBackupVaultRuns,
  type BackupVaultRun,
  type BackupVaultRunHistory,
} from '../api'

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

function StatusPill({ status }: { status: string | null }) {
  const value = (status || 'unknown').toLowerCase()
  return <span className={`bv-pill bv-pill--${value}`}>{value.toUpperCase()}</span>
}

type Props = {
  onLoaded?: (history: BackupVaultRunHistory) => void
}

export function BackupVaultRunHistory({ onLoaded }: Props) {
  const [history, setHistory] = useState<BackupVaultRunHistory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [targetFilter, setTargetFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const runs = await fetchBackupVaultRuns()
      setHistory(runs)
      onLoaded?.(runs)
      if (!runs.ok && runs.reason) setError(runs.reason)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load run history')
    } finally {
      setLoading(false)
    }
  }, [onLoaded])

  useEffect(() => {
    void load()
  }, [load])

  const targets = useMemo(() => {
    const names = new Set((history?.runs ?? []).map((r) => r.target_name).filter(Boolean))
    return [...names].sort()
  }, [history])

  const filtered = useMemo(() => {
    return (history?.runs ?? []).filter((run) => {
      if (targetFilter !== 'all' && run.target_name !== targetFilter) return false
      if (statusFilter !== 'all' && (run.status || '') !== statusFilter) return false
      return true
    })
  }, [history, targetFilter, statusFilter])

  if (loading && !history) {
    return <p className="muted">Loading run history…</p>
  }

  if (error && !history?.ok) {
    return <p className="banner error">{error}</p>
  }

  if (!history?.ok) {
    return <p className="muted">No BackupVault runs available from the portal database.</p>
  }

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Run history</h2>
          <p className="muted">
            {history.total} runs · {history.success_rate}% success — same jobs as backupvault.worktual.tech
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      <div className="bv-chip-row">
        <span className="bv-chip">
          TOTAL <strong>{history.total}</strong>
        </span>
        <span className="bv-chip bv-chip--ok">
          SUCCESS <strong>{history.success}</strong>
        </span>
        <span className="bv-chip bv-chip--fail">
          FAILED <strong>{history.failed}</strong>
        </span>
        <span className="bv-chip bv-chip--partial">
          PARTIAL <strong>{history.partial}</strong>
        </span>
        <span className="bv-chip bv-chip--run">
          RUNNING <strong>{history.running}</strong>
        </span>
      </div>

      <div className="bv-filters">
        <label>
          Target
          <select value={targetFilter} onChange={(e) => setTargetFilter(e.target.value)}>
            <option value="all">All targets</option>
            {targets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="partial">Partial</option>
            <option value="running">Running</option>
          </select>
        </label>
        {(targetFilter !== 'all' || statusFilter !== 'all') && (
          <button
            type="button"
            className="btn ghost"
            onClick={() => {
              setTargetFilter('all')
              setStatusFilter('all')
            }}
          >
            Clear
          </button>
        )}
      </div>

      <div className="table-wrap bv-runs-table">
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
            {filtered.map((run: BackupVaultRun) => (
              <tr key={run.id}>
                <td className="bv-mono">#{run.id}</td>
                <td>
                  <strong>{run.target_name}</strong>
                  {run.target_host ? <div className="muted bv-sub">{run.target_host}</div> : null}
                </td>
                <td className="bv-upper">{run.db_type ?? '—'}</td>
                <td>{run.backup_type ?? '—'}</td>
                <td>
                  <StatusPill status={run.status} />
                  {run.error_message ? (
                    <span className="bv-err-hint" title={run.error_message}>
                      i
                    </span>
                  ) : null}
                </td>
                <td>
                  {run.destination_count > 0
                    ? `${run.destination_count}${run.dest_types ? ` · ${run.dest_types}` : ''}`
                    : '—'}
                </td>
                <td>{run.file_size_label && run.file_size_bytes ? run.file_size_label : '—'}</td>
                <td>{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</td>
                <td>{formatDuration(run.duration_seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
