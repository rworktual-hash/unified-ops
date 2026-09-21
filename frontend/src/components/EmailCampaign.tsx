import { useMemo, useState } from 'react'
import type { EmailExtraEvent, EmailExtras } from '../api'
import { LIVE_EXTRAS_INTERVAL_MS } from '../useLivePoll'

const PERIODS: { label: string; hours: number }[] = [
  { label: '24h', hours: 24 },
  { label: '7 days', hours: 24 * 7 },
  { label: '30 days', hours: 24 * 30 },
]

type Props = {
  extras: EmailExtras | null
  loading?: boolean
  periodHours: number
  onPeriodHours: (hours: number) => void
}

function fmtTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value.includes('T') || value.includes('Z') ? value : value.replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function statusClass(status: string | null): string {
  const raw = (status || '').toLowerCase()
  if (raw.includes('bounce') || raw.includes('fail') || raw.includes('reach')) return 'email-status-bad'
  if (raw.includes('defer')) return 'email-status-warn'
  if (raw.includes('sent') || raw.includes('deliver')) return 'email-status-ok'
  return ''
}

export function EmailCampaign({ extras, loading = false, periodHours, onPeriodHours }: Props) {
  const [search, setSearch] = useState('')
  const [searchApplied, setSearchApplied] = useState('')
  const totals = extras?.totals
  const queue = extras?.queue
  const events = extras?.events ?? []
  const mix = useMemo(() => {
    const sent = totals?.sent ?? 0
    const bounce = totals?.bounce ?? 0
    const deferred = totals?.deferred ?? 0
    const unreachable = totals?.host_not_reachable ?? 0
    const sum = sent + bounce + deferred + unreachable
    return { sent, bounce, deferred, unreachable, sum }
  }, [totals])
  const filtered = useMemo(() => {
    const needle = searchApplied.trim().toLowerCase()
    if (!needle) return events
    return events.filter((row) => eventHaystack(row).includes(needle))
  }, [events, searchApplied])

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Campaign Bulk Mail</h2>
          <p className="muted email-sync-meta">
            Live SELECT from campaign-db <code>worktual_email_campaign</code>
            {extras?.database ? ` · ${extras.database}` : ''} — updates every {LIVE_EXTRAS_INTERVAL_MS / 1000}s.
            Gateways stay 84 / 80 for SSH.
          </p>
        </div>
        <div className="domain-tabs email-period-tabs" role="tablist" aria-label="Campaign period">
          {PERIODS.map((p) => (
            <button
              key={p.hours}
              type="button"
              role="tab"
              className={`domain-tab ${periodHours === p.hours ? 'active' : ''}`}
              onClick={() => onPeriodHours(p.hours)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading && !extras ? <p className="muted">Loading live campaign metrics…</p> : null}
      {extras && !extras.ok ? (
        <p className="muted">
          Campaign extras unavailable{extras.reason ? `: ${extras.reason}` : ''}. SSH tiles below still work.
        </p>
      ) : null}

      <div className="stat-row stat-row--email">
        <Kpi label="Sent" value={totals?.sent} accent />
        <Kpi label="Bounce" value={totals?.bounce} warn />
        <Kpi label="Deferred" value={totals?.deferred} />
        <Kpi label="Unreachable" value={totals?.host_not_reachable} warn />
        <Kpi label="Inbound" value={totals?.inbound} />
        <Kpi label="Outbound" value={totals?.outbound} />
        <Kpi label="Spam" value={totals?.spam} />
        <Kpi label="Quarantine" value={totals?.quarantine} />
      </div>

      {mix.sum > 0 ? (
        <div className="email-mix" aria-label="Delivery mix">
          <MixSeg label="Sent" value={mix.sent} total={mix.sum} color="#6d28d9" />
          <MixSeg label="Bounce" value={mix.bounce} total={mix.sum} color="#e11d48" />
          <MixSeg label="Deferred" value={mix.deferred} total={mix.sum} color="#d97706" />
          <MixSeg label="Unreachable" value={mix.unreachable} total={mix.sum} color="#334155" />
        </div>
      ) : null}

      <div className="stat-row stat-row--email">
        <Kpi label="Queued" value={queue?.queue_count} />
        <Kpi label="Queue deferred" value={queue?.deferred_count} warn />
        <Kpi label="Active" value={queue?.active_count} />
        <Kpi label="Incoming" value={queue?.incoming_count} />
        <Kpi label="Campaign queue" value={totals?.campaign_queued} />
        <Kpi label="Log rows" value={totals?.log_total} />
      </div>

      <h3 className="email-subhead">Delivery status (postfix snapshot)</h3>
      {extras?.servers.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Gateway</th>
                <th>Queued</th>
                <th>Deferred</th>
                <th>Active</th>
                <th>Incoming</th>
                <th>Top senders</th>
                <th>Snapshot</th>
              </tr>
            </thead>
            <tbody>
              {extras.servers.map((row) => (
                <tr key={row.server || row.inventory_name || row.server_name || String(row.snapshot_at)}>
                  <td>
                    {row.inventory_name || row.server_name || '—'}
                    <br />
                    <span className="muted">{row.server || '—'}</span>
                  </td>
                  <td>{row.queue_count}</td>
                  <td>{row.deferred_count}</td>
                  <td>{row.active_count}</td>
                  <td>{row.incoming_count}</td>
                  <td className="email-cell-subject">
                    {row.top_senders.length
                      ? row.top_senders.map((s) => `${s.sender} (${s.count})`).join(', ')
                      : '—'}
                  </td>
                  <td>{fmtTime(row.snapshot_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">No postfix_queue_snapshot rows yet.</p>
      )}

      <div className="panel-head email-live-logs-head">
        <h3 className="email-subhead">Live email logs</h3>
        <div className="email-search-row">
          <input
            type="search"
            className="email-search"
            placeholder="Search live from, to, subject, status…"
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
      {filtered.length === 0 ? (
        <p className="muted">No live log rows in this period.</p>
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
                <th>Class</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id}>
                  <td>{fmtTime(row.occurred_at)}</td>
                  <td>{row.event_type ?? '—'}</td>
                  <td>{row.direction ?? '—'}</td>
                  <td className="email-cell-addr">{row.from_addr ?? '—'}</td>
                  <td className="email-cell-addr">{row.to_addr ?? '—'}</td>
                  <td className="email-cell-subject" title={row.subject ?? undefined}>
                    {row.subject ?? '—'}
                  </td>
                  <td className={statusClass(row.status)}>{row.status ?? '—'}</td>
                  <td>{row.dsn ?? '—'}</td>
                  <td>{row.classification ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function eventHaystack(row: EmailExtraEvent): string {
  return [
    row.event_type,
    row.direction,
    row.from_addr,
    row.to_addr,
    row.subject,
    row.status,
    row.dsn,
    row.queue_id,
    row.classification,
    row.inventory_name,
    row.server,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function Kpi({
  label,
  value,
  accent,
  warn,
}: {
  label: string
  value: number | null | undefined
  accent?: boolean
  warn?: boolean
}) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className={`stat-value${accent ? ' accent' : ''}${warn ? ' warn' : ''}`}>
        {value == null ? '—' : value}
      </span>
    </div>
  )
}

function MixSeg({
  label,
  value,
  total,
  color,
}: {
  label: string
  value: number
  total: number
  color: string
}) {
  const pct = total ? Math.round((value / total) * 100) : 0
  if (!value) return null
  return (
    <div className="email-mix-seg" style={{ flexGrow: value, background: color }} title={`${label} ${value} (${pct}%)`}>
      {pct >= 12 ? `${label} ${pct}%` : ''}
    </div>
  )
}
