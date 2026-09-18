import { useCallback, useEffect, useState } from 'react'
import {
  fetchLegacyOverview,
  fetchLegacyStatus,
  syncLegacyMetrics,
  type LegacyOverview,
  type LegacyStatus,
} from '../api'

type Props = {
  domain: 'ai_insights' | 'backupvault' | 'voicemg' | 'infrastructure'
  title?: string
  isAdmin?: boolean
  hours?: number
}

export function LegacyMetricsSection({ domain, title, isAdmin = false, hours = 24 }: Props) {
  const [status, setStatus] = useState<LegacyStatus | null>(null)
  const [overview, setOverview] = useState<LegacyOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const stream = status?.streams.find((s) => s.domain === domain)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const st = await fetchLegacyStatus()
      setStatus(st)
      const streamRow = st.streams.find((s) => s.domain === domain)
      if (st.configured && streamRow && (streamRow.row_count > 0 || streamRow.enabled)) {
        setOverview(await fetchLegacyOverview(domain, hours))
      } else {
        setOverview(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load legacy metrics')
    } finally {
      setLoading(false)
    }
  }, [domain, hours])

  useEffect(() => {
    void load()
  }, [load])

  if (!status?.configured) {
    return (
      <section className="panel legacy-metrics-panel">
        <h2>{title ?? 'Legacy portal metrics'}</h2>
        <p className="muted">
          Not configured. SSH to server-management is <code>10.180.1.222:4204</code>; MySQL is usually{' '}
          <code>:3306</code>. Run <code>scripts/discover-legacy-mysql-via-ssh.py</code>, set{' '}
          <code>LEGACY_METRICS_DATABASE_URL</code>, then <code>inspect-legacy-metrics-db.py</code>, then
          enable the matching <code>LEGACY_*_SYNC_ENABLED</code> and table/column vars for this domain.
        </p>
      </section>
    )
  }

  return (
    <section className="panel legacy-metrics-panel">
      <div className="legacy-metrics-head">
        <h2>{title ?? 'Legacy portal metrics (server-management MySQL)'}</h2>
        {isAdmin ? (
          <button
            type="button"
            className="btn ghost"
            disabled={syncing || loading}
            onClick={() => {
              setSyncing(true)
              setError(null)
              void syncLegacyMetrics(domain)
                .then(() => load())
                .catch((err) =>
                  setError(err instanceof Error ? err.message : 'Legacy sync failed'),
                )
                .finally(() => setSyncing(false))
            }}
          >
            {syncing ? 'Syncing…' : 'Sync now'}
          </button>
        ) : null}
      </div>

      {error ? <p className="banner error">{error}</p> : null}

      <p className="muted legacy-metrics-meta">
        Connection: {status.connection_ok ? 'OK' : `Failed — ${status.connection_error ?? 'unknown'}`}
        {stream?.enabled ? ' · stream enabled' : ' · stream disabled (set LEGACY_*_SYNC_ENABLED=true after inspect)'}
        {stream?.last_synced_at
          ? ` · last sync ${new Date(stream.last_synced_at).toLocaleString()}`
          : ''}
        {stream?.last_error ? ` · error: ${stream.last_error}` : ''}
      </p>

      {loading ? <p className="muted">Loading legacy metrics…</p> : null}

      {overview && overview.point_count > 0 ? (
        <>
          <div className="stat-row">
            <div className="stat-card">
              <span className="stat-label">Points ({hours}h)</span>
              <span className="stat-value">{overview.point_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Hosts</span>
              <span className="stat-value">{overview.distinct_hosts}</span>
            </div>
            {Object.entries(overview.averages).map(([key, val]) => (
              <div className="stat-card" key={key}>
                <span className="stat-label">Avg {key}</span>
                <span className="stat-value">{val}</span>
              </div>
            ))}
          </div>

          {Object.keys(overview.status_counts).length > 0 ? (
            <p className="muted">
              Status breakdown:{' '}
              {Object.entries(overview.status_counts)
                .map(([k, v]) => `${k} (${v})`)
                .join(' · ')}
            </p>
          ) : null}

          {overview.latest_by_server.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Host</th>
                    <th>Latest</th>
                    <th>Metrics</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.latest_by_server.map((row) => (
                    <tr key={`${row.server_id ?? 'x'}-${row.server_name}`}>
                      <td>
                        {row.server_name}
                        {row.ip_address ? (
                          <>
                            <br />
                            <span className="muted">{row.ip_address}</span>
                          </>
                        ) : null}
                      </td>
                      <td>{new Date(row.latest_at).toLocaleString()}</td>
                      <td className="legacy-metrics-cells">
                        {Object.entries(row.metrics)
                          .map(([k, v]) => `${k}: ${v ?? '—'}`)
                          .join(' · ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : !loading ? (
        <p className="muted">
          No synced rows yet for <code>{domain}</code>
          {stream?.table ? ` (table ${stream.table})` : ''}. Run inspect script, set column names in .env,
          enable sync, then Sync now.
        </p>
      ) : null}
    </section>
  )
}
