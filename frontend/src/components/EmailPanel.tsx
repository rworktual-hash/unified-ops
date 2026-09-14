import { useCallback, useEffect, useState } from 'react'
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

export function EmailPanel({ emailServers, session }: Props) {
  const [overview, setOverview] = useState<EmailOverview | null>(null)
  const [events, setEvents] = useState<EmailLogEvent[]>([])
  const [queues, setQueues] = useState<Record<number, EmailQueueSnapshot | null>>({})
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    setOverview(await fetchEmailOverview(24))
    setEvents(await fetchEmailEvents(undefined, 200))
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
  }, [emailServers])

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : 'Failed to load email data'))
  }, [load])

  return (
    <>
      <header className="page-head">
        <h1>Email</h1>
        <p>
          Mail queue via SSH on email hosts; log analytics synced from email-management DB when configured.
        </p>
      </header>

      {error && <p className="banner error">{error}</p>}

      {overview && (
        <section className="panel">
          <div className="panel-head">
            <h2>Last {overview.period_hours}h (synced logs)</h2>
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
          {!overview.sync_configured && (
            <p className="muted">
              Set <code>EMAIL_MGMT_DATABASE_URL</code> on the API server and run{' '}
              <code>inspect-email-mgmt-db.py</code> — see docs/EMAIL_METRICS.md.
            </p>
          )}
          {overview.last_sync_error && (
            <p className="banner error">Last sync error: {overview.last_sync_error}</p>
          )}
          <div className="stat-row">
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
              <span className="stat-label">Delivered</span>
              <span className="stat-value accent">{overview.delivered}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Bounced</span>
              <span className="stat-value warn">{overview.bounced}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Failed</span>
              <span className="stat-value">{overview.failed}</span>
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
        <p className="muted">Use Collect metrics on Servers tab to refresh queue snapshots.</p>
      </section>

      <section className="panel">
        <h2>Recent mail events ({events.length})</h2>
        {events.length === 0 ? (
          <p className="muted">No synced events yet. Configure DB sync and run Sync mail logs.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Dir</th>
                  <th>From</th>
                  <th>To</th>
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
                    <td>{e.from_addr ?? '—'}</td>
                    <td>{e.to_addr ?? '—'}</td>
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
