type Props = {
  label: string
  valuePct: number | null
  display: string
  warnAt?: number
  critAt?: number
}

export function MetricBar({ label, valuePct, display, warnAt = 85, critAt = 92 }: Props) {
  const pct = valuePct != null ? Math.min(100, Math.max(0, valuePct)) : null
  let tone = 'ok'
  if (pct != null) {
    if (pct >= critAt) tone = 'crit'
    else if (pct >= warnAt) tone = 'warn'
  }

  return (
    <div className="metric-bar">
      <div className="metric-bar-head">
        <span className="metric-bar-label">{label}</span>
        <span className="metric-bar-value">{display}</span>
      </div>
      <div className="metric-bar-track">
        {pct != null ? (
          <div className={`metric-bar-fill ${tone}`} style={{ width: `${pct}%` }} />
        ) : (
          <div className="metric-bar-fill empty" />
        )}
      </div>
    </div>
  )
}
