import { useCallback, useEffect, useState } from 'react'
import { fetchBackupVaultDashboard, type BackupVaultDashboard } from '../api'
import { SimpleLineChart } from './SimpleLineChart'

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`
}

export function BackupVaultDashboard() {
  const [data, setData] = useState<BackupVaultDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchBackupVaultDashboard()
      setData(next)
      if (!next.ok && next.reason) setError(next.reason)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading && !data) return <p className="muted">Loading BackupVault dashboard…</p>
  if (error && !data?.ok) return <p className="banner error">{error}</p>
  if (!data) return null

  const history = data.history_14d.map((day, index) => ({ x: index, y: day.runs }))

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Dashboard</h2>
          <p className="muted">
            Read-only KPIs from MariaDB `backupvault` — no start / restore / query.
            {data.checked_at ? ` · checked ${new Date(data.checked_at).toLocaleString()}` : ''}
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      <div className="stat-row backupvault-stat-row">
        <Kpi label="Live DB servers" value={String(data.live_db_servers)} />
        <Kpi
          label="Today's runs"
          value={String(data.today_runs)}
          hint={`${data.today_success} success · ${data.today_failed} failed`}
        />
        <Kpi label="Failures (30d)" value={String(data.failures_30d)} />
        <Kpi
          label="Primary NFS"
          value={fmtPct(data.primary_nfs_pct)}
          hint={[data.primary_nfs_used, data.primary_nfs_size].filter(Boolean).join(' / ') || undefined}
        />
        <Kpi label="Data backed up" value={data.data_backed_up_label || '—'} />
        <Kpi
          label="Remote onsite"
          value={fmtPct(data.remote_pct)}
          hint={[data.remote_used, data.remote_size].filter(Boolean).join(' / ') || undefined}
        />
        <Kpi
          label="AWS S3 stored"
          value={data.s3_label || '—'}
          hint={data.s3_objects != null ? `${data.s3_objects} objects` : undefined}
        />
      </div>

      <div className="bv-dash-grid">
        <div>
          <h3 className="bv-group-title">Backup calendar — last 35 days</h3>
          <div className="bv-cal">
            {data.calendar.map((day) => (
              <span
                key={day.date}
                className={`bv-cal-day bv-cal-day--${day.tone}`}
                title={`${day.date}: ${day.success} ok · ${day.failed} fail · ${day.partial} partial`}
              >
                {Number(day.date.slice(-2))}
              </span>
            ))}
          </div>
          <p className="muted bv-sub">Green success · amber partial · red failed · empty no runs</p>
        </div>
        <SimpleLineChart
          title="14-day run history"
          points={history}
          yMin={0}
          emptyLabel="No runs in the last 14 days."
        />
      </div>
    </section>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint ? <span className="muted bv-sub">{hint}</span> : null}
    </div>
  )
}
