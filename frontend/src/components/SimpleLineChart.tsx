type Point = { x: number; y: number }

type Props = {
  title: string
  points: Point[]
  yMin?: number
  yMax?: number
  unit?: string
  height?: number
  emptyLabel?: string
}

const COLORS = ['#6d28d9', '#0891b2', '#ca8a04', '#dc2626', '#059669', '#7c3aed', '#ea580c', '#2563eb']

export function buildSeriesFromValues(
  values: (number | null | undefined)[],
  startIndex = 0,
): Point[] {
  const out: Point[] = []
  values.forEach((v, i) => {
    if (v != null && !Number.isNaN(v)) out.push({ x: startIndex + i, y: v })
  })
  return out
}

export function SimpleLineChart({
  title,
  points,
  yMin,
  yMax,
  unit = '',
  height = 72,
  emptyLabel = 'No data yet — run scheduled collect or Collect metrics',
}: Props) {
  const width = 280
  const pad = { t: 8, r: 8, b: 18, l: 36 }
  const innerW = width - pad.l - pad.r
  const innerH = height - pad.t - pad.b

  if (points.length === 0) {
    return (
      <div className="chart-block">
        <div className="chart-title">{title}</div>
        <p className="chart-empty">{emptyLabel}</p>
      </div>
    )
  }

  const ys = points.map((p) => p.y)
  const minY = yMin ?? Math.min(...ys)
  const maxY = yMax ?? Math.max(...ys)
  const spanY = maxY - minY || 1
  const minX = points[0].x
  const maxX = points[points.length - 1].x
  const spanX = maxX - minX || 1

  const toPath = (pts: Point[]) =>
    pts
      .map((p, i) => {
        const px = pad.l + ((p.x - minX) / spanX) * innerW
        const py = pad.t + innerH - ((p.y - minY) / spanY) * innerH
        return `${i === 0 ? 'M' : 'L'} ${px.toFixed(1)} ${py.toFixed(1)}`
      })
      .join(' ')

  const last = points[points.length - 1]

  return (
    <div className="chart-block">
      <div className="chart-head">
        <span className="chart-title">{title}</span>
        <span className="chart-last">
          {last.y.toFixed(1)}
          {unit}
        </span>
      </div>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img">
        <text x={pad.l} y={height - 4} className="chart-axis-label">
          {minY.toFixed(0)}
          {unit}
        </text>
        <text x={width - pad.r - 24} y={height - 4} className="chart-axis-label">
          {maxY.toFixed(0)}
          {unit}
        </text>
        <path d={toPath(points)} fill="none" stroke={COLORS[0]} strokeWidth="1.5" />
      </svg>
    </div>
  )
}

export function MultiLineChart({
  title,
  series,
  yMin = 0,
  yMax = 100,
  unit = '%',
  height = 88,
}: {
  title: string
  series: { label: string; points: Point[]; colorIndex?: number }[]
  yMin?: number
  yMax?: number
  unit?: string
  height?: number
}) {
  const width = 280
  const pad = { t: 8, r: 8, b: 18, l: 8 }
  const innerW = width - pad.l - pad.r
  const innerH = height - pad.t - pad.b
  const all = series.flatMap((s) => s.points)
  if (all.length === 0) {
    return (
      <div className="chart-block">
        <div className="chart-title">{title}</div>
        <p className="chart-empty">No data yet</p>
      </div>
    )
  }
  const minX = Math.min(...all.map((p) => p.x))
  const maxX = Math.max(...all.map((p) => p.x))
  const spanX = maxX - minX || 1
  const spanY = yMax - yMin || 1

  const pathFor = (pts: Point[]) =>
    pts
      .map((p, i) => {
        const px = pad.l + ((p.x - minX) / spanX) * innerW
        const py = pad.t + innerH - ((p.y - yMin) / spanY) * innerH
        return `${i === 0 ? 'M' : 'L'} ${px.toFixed(1)} ${py.toFixed(1)}`
      })
      .join(' ')

  return (
    <div className="chart-block chart-block-wide">
      <div className="chart-title">{title}</div>
      <div className="chart-legend">
        {series.map((s, i) => (
          <span key={s.label} className="chart-legend-item">
            <span
              className="chart-legend-swatch"
              style={{ background: COLORS[s.colorIndex ?? i % COLORS.length] }}
            />
            {s.label}
          </span>
        ))}
      </div>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img">
        {series.map((s, i) =>
          s.points.length > 0 ? (
            <path
              key={s.label}
              d={pathFor(s.points)}
              fill="none"
              stroke={COLORS[s.colorIndex ?? i % COLORS.length]}
              strokeWidth="1.2"
            />
          ) : null,
        )}
      </svg>
      <span className="chart-axis-hint">
        0{unit} – {yMax}
        {unit}
      </span>
    </div>
  )
}
