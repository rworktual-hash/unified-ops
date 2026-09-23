import { useMemo, useState } from 'react'
import type { AiInsightExtra, AiInsightHistoryRange } from '../api'
import { LIVE_EXTRAS_INTERVAL_MS } from '../useLivePoll'
import { AiInsightsCharts, buildGroupRows } from './AiInsightsCharts'
import { AiInsightsHistory } from './AiInsightsHistory'

const HISTORY_RANGES: Array<{ id: AiInsightHistoryRange; label: string }> = [
  { id: '30m', label: '30 min' },
  { id: '60m', label: '60 min' },
  { id: '2h', label: '2 hours' },
  { id: 'today', label: 'Today' },
]

function healthClass(score: number | null): string {
  if (score == null) return 'unknown'
  if (score >= 80) return 'ok'
  if (score >= 60) return 'partial'
  return 'fail'
}

function isOnline(row: AiInsightExtra): boolean {
  const status = (row.health_status || '').toLowerCase()
  if (status === 'healthy' || status === 'ok' || status === 'online' || status === 'up') return true
  if (status === 'unhealthy' || status === 'down' || status === 'critical') return false
  return (row.health_score ?? 0) >= 80
}

function avg(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((v): v is number => v != null && !Number.isNaN(v))
  if (!nums.length) return null
  return nums.reduce((sum, n) => sum + n, 0) / nums.length
}

type Props = {
  extras: AiInsightExtra[]
  onOpenHost?: (row: AiInsightExtra) => boolean
}

export function AiInsightsGroups({ extras, onOpenHost }: Props) {
  const [filter, setFilter] = useState('all')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [historyRange, setHistoryRange] = useState<AiInsightHistoryRange>('60m')
  const groups = useMemo(() => buildGroupRows(extras), [extras])
  const rows = useMemo(() => {
    if (filter === 'all') return extras
    return extras.filter((row) => (row.group_id || 'other') === filter)
  }, [extras, filter])
  const selected = rows.find((row) => row.id === selectedId) ?? null
  const title = filter === 'all' ? 'All Servers' : groups.find((g) => g.id === filter)?.label || 'Group'
  const kpis = {
    servers: rows.length,
    online: rows.filter(isOnline).length,
    health: avg(rows.map((r) => r.health_score)),
    alerts: rows.reduce((sum, r) => sum + (r.open_alerts || 0), 0),
  }
  const ok = rows.filter((r) => (r.health_score ?? 0) >= 80).length
  const warn = rows.filter((r) => r.health_score != null && r.health_score >= 60 && r.health_score < 80).length
  const fail = rows.filter((r) => r.health_score != null && r.health_score < 60).length

  if (!extras.length) return null

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>AI Insights groups</h2>
          <p className="muted">
            Live from MariaDB <code>ai_insights_platform</code> — updates every{' '}
            {LIVE_EXTRAS_INTERVAL_MS / 1000}s. Click a host to open it.
          </p>
        </div>
      </div>

      <div className="bv-tabs" role="tablist" aria-label="AI Insights groups">
        <button
          type="button"
          className={`bv-tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All Servers <span className="domain-tab-count">{extras.length}</span>
        </button>
        {groups.map((group) => (
          <button
            key={group.id}
            type="button"
            className={`bv-tab ${filter === group.id ? 'active' : ''}`}
            onClick={() => setFilter(group.id)}
          >
            {group.label} <span className="domain-tab-count">{group.servers.length}</span>
          </button>
        ))}
      </div>

      <h3 className="bv-group-title">{title}</h3>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Servers</span>
          <span className="stat-value">{kpis.servers}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Online</span>
          <span className="stat-value">{kpis.online}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Avg health</span>
          <span className="stat-value">{kpis.health == null ? '—' : Math.round(kpis.health)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Open alerts</span>
          <span className="stat-value warn">{kpis.alerts}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Health split</span>
          <span className="stat-value">
            {ok}/{warn}/{fail}
          </span>
          <span className="muted bv-sub">ok / fair / poor</span>
        </div>
      </div>

      <AiInsightsCharts
        extras={extras}
        filter={filter}
        onSelectGroup={(id) => setFilter((prev) => (prev === id ? 'all' : id))}
      />

      <div className="ai-history-toolbar">
        <div className="bv-tabs" role="tablist" aria-label="AI Insights history range">
          {HISTORY_RANGES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`bv-tab ${historyRange === item.id ? 'active' : ''}`}
              onClick={() => setHistoryRange(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <p className="muted bv-sub">Click a host to open its charts and metrics.</p>
      </div>
      <AiInsightsHistory
        range={historyRange}
        group={filter}
        serverId={selected?.id ?? null}
        hostName={selected?.server_name ?? null}
      />

      <div className="ai-group-cards">
        {rows.map((row) => (
          <button
            key={row.id}
            type="button"
            className={`ai-group-card ${selectedId === row.id ? 'active' : ''}`}
            onClick={() => {
              if (onOpenHost?.(row)) return
              setSelectedId((prev) => (prev === row.id ? null : row.id))
            }}
          >
            <div className="ai-extra-head">
              <span className="muted">{row.group || row.server_type || 'Host'}</span>
              <span className={`bv-pill bv-pill--${healthClass(row.health_score)}`}>
                {row.health_status || '—'}
              </span>
            </div>
            <h3>{row.server_name}</h3>
            <p className={`ai-group-score ai-group-score--${healthClass(row.health_score)}`}>
              {row.health_score ?? '—'}
            </p>
            <p className="muted bv-sub">{row.ip_address || row.hostname || ''}</p>
            <p className="muted bv-sub" title={row.extras.map((t) => `${t.label} ${t.value}`).join(' · ')}>
              {row.extras.slice(0, 4).map((tile) => `${tile.label} ${tile.value}`).join(' · ') || 'No service tiles'}
            </p>
            {row.open_alerts > 0 ? (
              <p className="muted bv-sub">{row.open_alerts} open alerts</p>
            ) : null}
          </button>
        ))}
      </div>
    </section>
  )
}
