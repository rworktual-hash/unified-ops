import type { AiInsightExtra } from '../api'

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`
}

function healthClass(score: number | null): string {
  if (score == null) return 'unknown'
  if (score >= 80) return 'ok'
  if (score >= 60) return 'partial'
  return 'fail'
}

type Props = {
  extra: AiInsightExtra
  compact?: boolean
}

export function AiInsightExtras({ extra, compact = false }: Props) {
  const tiles = extraTiles(extra)
  if (compact) {
    const bits = [
      extra.health_score != null ? `health ${extra.health_score}` : null,
      ...extra.extras.slice(0, 3).map((tile) => `${tile.label} ${tile.value}`),
    ].filter(Boolean)
    return (
      <span className="ai-extra-line" title={bits.join(' · ')}>
        {extra.health_score != null ? (
          <span className={`bv-pill bv-pill--${healthClass(extra.health_score)}`}>
            {extra.health_score}
          </span>
        ) : null}
        {bits.length ? <span className="muted bv-sub">{bits.join(' · ')}</span> : '—'}
      </span>
    )
  }

  return (
    <div className="ai-extra-block">
      <div className="ai-extra-head">
        <span className="metric-label">AI Insights extras</span>
        {extra.health_score != null ? (
          <span className={`bv-pill bv-pill--${healthClass(extra.health_score)}`}>
            health {extra.health_score}
            {extra.health_status ? ` · ${extra.health_status}` : ''}
          </span>
        ) : null}
      </div>
      <div className="metric-grid gpu-metrics">
        {tiles.map((tile) => (
          <div className="metric-tile" key={tile.key}>
            <span className="metric-label">{tile.label}</span>
            <span className="metric-value">{tile.value}</span>
          </div>
        ))}
      </div>
      {extra.recorded_at ? (
        <p className="muted bv-sub">Portal {new Date(extra.recorded_at).toLocaleString()}</p>
      ) : null}
    </div>
  )
}

function extraTiles(extra: AiInsightExtra): { key: string; label: string; value: string }[] {
  const base: { key: string; label: string; value: string }[] = []
  if (extra.cpu_utilization != null) {
    base.push({ key: 'cpu', label: 'CPU util', value: fmtPct(extra.cpu_utilization) })
  }
  if (extra.memory_utilization != null) {
    base.push({ key: 'mem', label: 'Memory', value: fmtPct(extra.memory_utilization) })
  }
  if (extra.gpu_utilization != null) {
    base.push({ key: 'gpu', label: 'GPU util', value: fmtPct(extra.gpu_utilization) })
  }
  if (extra.gpu_temperature != null) {
    base.push({ key: 'gputemp', label: 'GPU temp', value: `${extra.gpu_temperature.toFixed(1)}°C` })
  }
  if (extra.open_alerts > 0) {
    base.push({ key: 'alerts', label: 'Open alerts', value: String(extra.open_alerts) })
  }
  const seen = new Set(base.map((t) => t.key))
  for (const tile of extra.extras) {
    if (seen.has(tile.key)) continue
    base.push(tile)
    seen.add(tile.key)
    if (base.length >= 10) break
  }
  return base
}
