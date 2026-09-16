import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchEmailEvents,
  fetchEmailOverview,
  fetchEmailQueue,
  syncEmailLogs,
  type AppUser,
  type EmailLogEvent,
  type EmailOverview,
  type EmailQueueSnapshot,
} from '../api'
import type { Server } from '../types'

type Props = {
  emailServers: Server[]
  session: AppUser
}

const PERIOD_HOURS: { label: string; hours: number }[] = [
  { label: '24h', hours: 24 },
  { label: '7 days', hours: 24 * 7 },
  { label: '30 days', hours: 24 * 30 },
]

export function EmailPanel({ emailServers, session }: Props) {
  const [periodHours, setPeriodHours] = useState(24)
  const [overview, setOverview] = useState<EmailOverview | null>(null)
  const [events, setEvents] = useState<EmailLogEvent[]>([])
  const [search, setSearch] = useState('')
  const [searchApplied, setSearchApplied] = useState('')
  const [queues, setQueues] = useState<Record<number, EmailQueueSnapshot | null>>({})
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    setOverview(await fetchEmailOverview(periodHours))
    setEvents(
      await fetchEmailEvents(undefined, periodHours, searchApplied.trim() || undefined, 200),
    )
    const q: Record<number, EmailQueueSnapshot | null> = {}
    await Promise.all(
      emailServers.map(async (s) => {
        try {
          q[s.id] = await fetchEmailQueue(s.id)
        } catch {
          q[s.id] = null
        }
      }),
    )
    setQueues(q)
  }, [emailServers, periodHours, searchApplied])

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : 'Failed to load email data'))
  }, [load])

  const lastUpdated = useMemo(() => {
    if (!overview?.last_synced_at) return null
    return new Date(overview.last_synced_at).toLocaleString()
  }, [overview?.last_synced_at])

  return (
    <>
      <header className="page-head">
        <h1>Email</h1>
        <p>
          Read-only: Postfix queue via SSH; mail log rows copied from email-management DB into Unified Ops
          (no sends, queue deletes, or remote DB writes).
        </p>
      </header>

      {error && <p className="banner error">{error}</p>}

      {overview && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Email logs &amp; analytics</h2>
              <p className="muted email-sync-meta">
                Synced copy · {events.length} events shown
                {lastUpdated ? ` · Last sync ${lastUpdated}` : ''}
                {overview.scheduled_sync_enabled ? ' · Auto-sync on (Celery)' : ''}
              </p>
            </div>
            <div className="email-toolbar">
              <div className="domain-tabs email-period-tabs" role="tablist" aria-label="Period">
                {PERIOD_HOURS.map((p) => (
                  <button
                    key={p.hours}
                    type="button"
                    role="tab"
                    className={`domain-tab ${periodHours === p.hours ? 'active' : ''}`}
                    onClick={() => setPeriodHours(p.hours)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              {session.role === 'admin' && (
                <button
                  type="button"
                  className="btn primary"
                  disabled={syncing || !overview.sync_configured}
                  onClick={async () => {
                    setSyncing(true)
                    try {
                      await syncEmailLogs()
                      await load()
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Sync failed')
                    } finally {
                      setSyncing(false)
                    }
                  }}
                >
                  {syncing ? 'Syncing…' : 'Sync mail logs'}
                </button>
              )}
            </div>
          </div>
          {!overview.sync_configured && (
            <p className="muted">
              Set <code>EMAIL_MGMT_DATABASE_URL</code> on the API server (read-only DB user) and run{' '}
              <code>inspect-email-mgmt-db.py</code> — see docs/EMAIL_METRICS.md.
            </p>
          )}
          {overview.last_sync_error && (
            <p className="banner error">Last sync error: {overview.last_sync_error}</p>
          )}
          <div className="stat-row stat-row--email">
            <div className="stat-card">
              <span className="stat-label">Total</span>
              <span className="stat-value">{overview.total}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Inbound</span>
              <span className="stat-value">{overview.inbound}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Outbound</span>
              <span className="stat-value">{overview.outbound}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Blocked</span>
              <span className="stat-value">{overview.blocked ?? 0}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Wrong hits</span>
              <span className="stat-value warn">{overview.wrong_hits ?? 0}</span>
            </div>
          </div>
          <div className="stat-row stat-row--email">
            <div className="stat-card">
              <span className="stat-label">Delivered</span>
              <span className="stat-value accent">{overview.delivered}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Failed</span>
              <span className="stat-value">{overview.failed}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Bounced</span>
              <span className="stat-value warn">{overview.bounced}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Deferred</span>
              <span className="stat-value">{overview.deferred ?? 0}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Timed out</span>
              <span className="stat-value">{overview.timed_out ?? 0}</span>
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <h2>Postfix queue (SSH)</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Server</th>
                <th>Postfix</th>
                <th>Queued</th>
                <th>Size (KB)</th>
              </tr>
            </thead>
            <tbody>
              {emailServers.map((s) => {
                const q = queues[s.id]
                return (
                  <tr key={s.id}>
                    <td>
                      {s.server_name}
                      <br />
                      <span className="muted">{s.ip_address}</span>
                    </td>
                    <td>{q?.postfix_active == null ? '—' : q.postfix_active ? 'active' : 'down'}</td>
                    <td>{q?.queue_messages ?? '—'}</td>
                    <td>{q?.queue_size_kb ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="muted">Refresh via fleet collect or Collect metrics on Servers.</p>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Recent mail events</h2>
          <div className="email-search-row">
            <input
              type="search"
              className="email-search"
              placeholder="Search email, subject, queue ID, status…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setSearchApplied(search)
              }}
            />
            <button type="button" className="btn ghost" onClick={() => setSearchApplied(search)}>
              Search
            </button>
          </div>
        </div>
        {events.length === 0 ? (
          <p className="muted">No synced events in this period. Configure DB sync and run Sync mail logs.</p>
        ) : (
          <div className="table-wrap email-events-table">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Dir</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Subject</th>
                  <th>Status</th>
                  <th>DSN</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td>{new Date(e.occurred_at).toLocaleString()}</td>
                    <td>{e.event_type ?? '—'}</td>
                    <td>{e.direction ?? '—'}</td>
                    <td className="email-cell-addr">{e.from_addr ?? '—'}</td>
                    <td className="email-cell-addr">{e.to_addr ?? '—'}</td>
                    <td className="email-cell-subject" title={e.subject ?? undefined}>
                      {e.subject ?? '—'}
                    </td>
                    <td>{e.status ?? '—'}</td>
                    <td>{e.dsn ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
