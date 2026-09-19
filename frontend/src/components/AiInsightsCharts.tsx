import { useMemo, useState } from 'react'
import type { AiInsightExtra } from '../api'

export const GROUP_ORDER = [
  'ai',
  'nginx',
  'kong',
  'redis',
  'mysql',
  'postgres',
  'mail',
  'voicemg',
  'pbx',
  'sip',
  'cpu',
  'other',
] as const

const GROUP_COLORS: Record<string, string> = {
  ai: '#4f46e5',
  nginx: '#0e7490',
  kong: '#7c3aed',
  redis: '#e11d48',
  mysql: '#0369a1',
  postgres: '#1d4ed8',
  mail: '#b45309',
  voicemg: '#0f766e',
  pbx: '#c2410c',
  sip: '#4338ca',
  cpu: '#334155',
  other: '#64748b',
}

const HEALTH = {
  ok: '#059669',
  warn: '#d97706',
  fail: '#e11d48',
}

export type GroupRow = {
  id: string
  label: string
  servers: AiInsightExtra[]
}

function avg(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((v): v is number => v != null && !Number.isNaN(v))
  if (!nums.length) return null
  return nums.reduce((sum, n) => sum + n, 0) / nums.length
}

function healthBand(score: number | null): 'ok' | 'warn' | 'fail' | 'unknown' {
  if (score == null) return 'unknown'
  if (score >= 80) return 'ok'
  if (score >= 60) return 'warn'
  return 'fail'
}

export function buildGroupRows(extras: AiInsightExtra[]): GroupRow[] {
  const byId = new Map<string, GroupRow>()
  for (const row of extras) {
    const id = row.group_id || 'other'
    const current = byId.get(id) ?? { id, label: row.group || 'Other', servers: [] }
    current.servers.push(row)
    byId.set(id, current)
  }
  return GROUP_ORDER.map((id) => byId.get(id)).filter((g): g is GroupRow => Boolean(g))
}

type Props = {
  extras: AiInsightExtra[]
  filter: string
  onSelectGroup: (id: string) => void
}

export function AiInsightsCharts({ extras, filter, onSelectGroup }: Props) {
  const groups = useMemo(() => buildGroupRows(extras), [extras])
  const scoped = filter === 'all' ? extras : extras.filter((row) => (row.group_id || 'other') === filter)
  const mix = useMemo(
    () =>
      groups.map((group) => ({
        id: group.id,
        label: group.label,
        color: GROUP_COLORS[group.id] || GROUP_COLORS.other,
        count: group.servers.length,
        health: avg(group.servers.map((s) => s.health_score)),
        ok: group.servers.filter((s) => healthBand(s.health_score) === 'ok').length,
        warn: group.servers.filter((s) => healthBand(s.health_score) === 'warn').length,
        fail: group.servers.filter((s) => healthBand(s.health_score) === 'fail').length,
        unknown: group.servers.filter((s) => healthBand(s.health_score) === 'unknown').length,
        cpu: avg(group.servers.map((s) => s.cpu_utilization)),
        mem: avg(group.servers.map((s) => s.memory_utilization)),
        disk: avg(group.servers.map((s) => s.storage_utilization)),
      })),
    [groups],
  )
  const healthMix = [
    { id: 'ok', label: 'Healthy ≥80', color: HEALTH.ok, count: scoped.filter((s) => healthBand(s.health_score) === 'ok').length },
    { id: 'warn', label: 'Fair 60–79', color: HEALTH.warn, count: scoped.filter((s) => healthBand(s.health_score) === 'warn').length },
    { id: 'fail', label: 'Poor <60', color: HEALTH.fail, count: scoped.filter((s) => healthBand(s.health_score) === 'fail').length },
  ]
  const title = filter === 'all' ? 'All groups' : mix.find((g) => g.id === filter)?.label || 'Group'

  return (
    <div className="ai-charts">
      <div className="ai-charts-grid">
        <article className="ai-chart-card">
          <header>
            <h3>Fleet composition</h3>
            <p className="muted">Hosts per group · click a slice or row to filter</p>
          </header>
          <div className="ai-chart-split">
            <Donut
              segments={mix.map((g) => ({
                id: g.id,
                label: g.label,
                value: g.count,
                color: g.color,
              }))}
              activeId={filter === 'all' ? null : filter}
              centerValue={String(extras.length)}
              centerLabel="hosts"
              onSelect={onSelectGroup}
            />
            <Legend
              items={mix.map((g) => ({
                id: g.id,
                label: g.label,
                value: g.count,
                color: g.color,
              }))}
              activeId={filter === 'all' ? null : filter}
              onSelect={onSelectGroup}
            />
          </div>
        </article>

        <article className="ai-chart-card">
          <header>
            <h3>Health mix · {title}</h3>
            <p className="muted">Same live scores as aiservers.worktual.tech</p>
          </header>
          <div className="ai-chart-split">
            <Donut
              segments={healthMix.map((g) => ({
                id: g.id,
                label: g.label,
                value: g.count,
                color: g.color,
              }))}
              centerValue={String(scoped.length)}
              centerLabel="in view"
            />
            <Legend
              items={healthMix.map((g) => ({
                id: g.id,
                label: g.label,
                value: g.count,
                color: g.color,
              }))}
            />
          </div>
        </article>
      </div>

      <article className="ai-chart-card">
        <header>
          <h3>Group health stack</h3>
          <p className="muted">Healthy / fair / poor share of each group</p>
        </header>
        <div className="ai-stack-list">
          {mix.map((group) => {
            const total = group.ok + group.warn + group.fail + group.unknown || 1
            return (
              <button
                key={group.id}
                type="button"
                className={`ai-stack-row ${filter === group.id ? 'active' : ''}`}
                onClick={() => onSelectGroup(group.id)}
              >
                <span className="ai-stack-label">{group.label}</span>
                <span className="ai-stack-track" aria-hidden>
                  <span style={{ width: `${(group.ok / total) * 100}%`, background: HEALTH.ok }} />
                  <span style={{ width: `${(group.warn / total) * 100}%`, background: HEALTH.warn }} />
                  <span style={{ width: `${(group.fail / total) * 100}%`, background: HEALTH.fail }} />
                  <span style={{ width: `${(group.unknown / total) * 100}%`, background: '#94a3b8' }} />
                </span>
                <span className="ai-stack-meta">
                  {group.count}
                  {group.health != null ? ` · ${Math.round(group.health)}` : ''}
                </span>
              </button>
            )
          })}
        </div>
      </article>

      <article className="ai-chart-card">
        <header>
          <h3>Resource pressure</h3>
          <p className="muted">Average CPU / RAM / disk from MariaDB extras</p>
        </header>
        <div className="ai-util-table">
          {mix.map((group) => (
            <button
              key={group.id}
              type="button"
              className={`ai-util-row ${filter === group.id ? 'active' : ''}`}
              onClick={() => onSelectGroup(group.id)}
            >
              <span className="ai-stack-label">{group.label}</span>
              <Meter label="CPU" value={group.cpu} />
              <Meter label="RAM" value={group.mem} />
              <Meter label="Disk" value={group.disk} />
            </button>
          ))}
        </div>
      </article>
    </div>
  )
}

type Segment = { id: string; label: string; value: number; color: string }

function Donut({
  segments,
  centerValue,
  centerLabel,
  activeId,
  onSelect,
}: {
  segments: Segment[]
  centerValue: string
  centerLabel: string
  activeId?: string | null
  onSelect?: (id: string) => void
}) {
  const [hover, setHover] = useState<string | null>(null)
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1
  const size = 176
  const thickness = 22
  const r = (size - thickness) / 2
  const circ = 2 * Math.PI * r
  let offset = 0
  const hovered = segments.find((s) => s.id === hover)

  return (
    <div className="ai-donut-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={thickness} />
        {segments.map((seg) => {
          if (seg.value <= 0) return null
          const len = (seg.value / total) * circ
          const node = (
            <circle
              key={seg.id}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={activeId === seg.id || hover === seg.id ? thickness + 3 : thickness}
              strokeDasharray={`${len} ${circ - len}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              className={onSelect ? 'ai-donut-slice' : undefined}
              onMouseEnter={() => setHover(seg.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect?.(seg.id)}
            />
          )
          offset += len
          return node
        })}
      </svg>
      <div className="ai-donut-center">
        <strong>{hovered ? hovered.value : centerValue}</strong>
        <span>{hovered ? hovered.label : centerLabel}</span>
      </div>
    </div>
  )
}

function Legend({
  items,
  activeId,
  onSelect,
}: {
  items: Segment[]
  activeId?: string | null
  onSelect?: (id: string) => void
}) {
  const total = items.reduce((sum, s) => sum + s.value, 0) || 1
  return (
    <ul className="ai-legend">
      {items.map((item) => {
        const pct = Math.round((item.value / total) * 100)
        const body = (
          <>
            <span className="ai-legend-swatch" style={{ background: item.color }} />
            <span className="ai-legend-label">{item.label}</span>
            <span className="ai-legend-value">
              {item.value} · {pct}%
            </span>
          </>
        )
        return (
          <li key={item.id}>
            {onSelect ? (
              <button
                type="button"
                className={`ai-legend-btn ${activeId === item.id ? 'active' : ''}`}
                onClick={() => onSelect(item.id)}
              >
                {body}
              </button>
            ) : (
              <div className="ai-legend-btn">{body}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function Meter({ label, value }: { label: string; value: number | null }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value))
  const tone = value == null ? 'unknown' : value >= 85 ? 'fail' : value >= 70 ? 'warn' : 'ok'
  return (
    <span className="ai-meter">
      <span className="ai-meter-label">{label}</span>
      <span className="ai-meter-track">
        <span className={`ai-meter-fill ai-meter-fill--${tone}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="ai-meter-val">{value == null ? '—' : `${Math.round(value)}%`}</span>
    </span>
  )
}
