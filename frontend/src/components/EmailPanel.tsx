import { useCallback, useEffect, useState } from 'react'
import {
  fetchEmailExtras,
  fetchEmailQueue,
  fetchEmailSshOverview,
  type AppUser,
  type EmailExtras,
  type EmailQueueSnapshot,
  type EmailSshOverview,
} from '../api'
import { useLivePoll } from '../useLivePoll'
import type { Server } from '../types'
import { EmailCampaign } from './EmailCampaign'

type Props = {
  emailServers: Server[]
  session: AppUser
}

export function EmailPanel({ emailServers, session: _session }: Props) {
  const [campaignHours, setCampaignHours] = useState(24)
  const [extras, setExtras] = useState<EmailExtras | null>(null)
  const [extrasLoading, setExtrasLoading] = useState(true)
  const [queues, setQueues] = useState<Record<number, EmailQueueSnapshot | null>>({})
  const [sshOverview, setSshOverview] = useState<EmailSshOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadExtras = useCallback(async () => {
    try {
      const data = await fetchEmailExtras(campaignHours)
      setExtras(data)
    } catch {
      /* keep last extras */
    } finally {
      setExtrasLoading(false)
    }
  }, [campaignHours])

  const load = useCallback(async () => {
    setError(null)
    setSshOverview(await fetchEmailSshOverview())
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

  useEffect(() => {
    setExtrasLoading(true)
    void loadExtras()
  }, [loadExtras])
  useLivePoll(loadExtras, true)

  const sshHasTotals = Boolean(
    sshOverview &&
      [sshOverview.total_received, sshOverview.total_delivered, sshOverview.total_bounced].some((v) => v != null),
  )

  return (
    <>
      <header className="page-head">
        <h1>Email</h1>
        <p>
          Live Campaign from campaign-db <code>10.180.0.203</code>. Gateways 84 / 80 are SSH only.
        </p>
      </header>

      {error && <p className="banner error">{error}</p>}

      <EmailCampaign
        extras={extras}
        loading={extrasLoading}
        periodHours={campaignHours}
        onPeriodHours={setCampaignHours}
      />

      {sshOverview ? (
        <section className="panel">
          <h2>Gateways (SSH)</h2>
          <p className="muted email-sync-meta">
            Host health on 84 / 80 / 0.84. Refresh with Collect on Servers. Not the campaign DB.
          </p>
          {sshHasTotals ? (
            <div className="stat-row stat-row--email">
              <div className="stat-card">
                <span className="stat-label">Received</span>
                <span className="stat-value">{sshOverview.total_received ?? '—'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Delivered</span>
                <span className="stat-value accent">{sshOverview.total_delivered ?? '—'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Bounced</span>
                <span className="stat-value warn">{sshOverview.total_bounced ?? '—'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Rejected</span>
                <span className="stat-value">{sshOverview.total_rejected ?? '—'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Deferred</span>
                <span className="stat-value">{sshOverview.total_deferred ?? '—'}</span>
              </div>
            </div>
          ) : (
            <p className="muted">No today-counts yet. Last collect is old or incomplete — run Collect on the email hosts.</p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Server</th>
                  <th>Postfix</th>
                  <th>Queued</th>
                  <th>Size (KB)</th>
                  <th>Collected</th>
                </tr>
              </thead>
              <tbody>
                {emailServers.map((s) => {
                  const q = queues[s.id]
                  const row = sshOverview.servers.find((r) => r.server_id === s.id)
                  const collected = row?.snapshot?.collected_at || q?.collected_at
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
                      <td>{collected ? new Date(collected).toLocaleString() : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </>
  )
}
