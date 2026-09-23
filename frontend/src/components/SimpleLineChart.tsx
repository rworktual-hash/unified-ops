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

function ordered(points: Point[]): Point[] {
  return [...points].sort((a, b) => a.x - b.x)
}

function linePath(points: Point[], minX: number, spanX: number, minY: number, spanY: number): string {
  const plotW = 100
  const plotH = 100
  return ordered(points)
    .map((p, i) => {
      const px = ((p.x - minX) / spanX) * plotW
      const py = plotH - ((p.y - minY) / spanY) * plotH
      return `${i === 0 ? 'M' : 'L'} ${px.toFixed(2)} ${py.toFixed(2)}`
    })
    .join(' ')
}

export function SimpleLineChart({
  title,
  points,
  yMin,
  yMax,
  unit = '',
  height = 120,
  emptyLabel = 'No data yet — run scheduled collect or Collect metrics',
}: Props) {
  if (points.length === 0) {
    return (
      <div className="chart-block">
        <div className="chart-title">{title}</div>
        <p className="chart-empty">{emptyLabel}</p>
      </div>
    )
  }

  const series = ordered(points)
  const ys = series.map((p) => p.y)
  const minY = yMin ?? Math.min(...ys)
  const maxY = yMax ?? Math.max(...ys)
  const spanY = maxY - minY || 1
  const minX = series[0].x
  const maxX = series[series.length - 1].x
  const spanX = maxX - minX || 1
  const last = series[series.length - 1]

  return (
    <div className="chart-block">
      <div className="chart-head">
        <span className="chart-title">{title}</span>
        <span className="chart-last">
          {last.y.toFixed(1)}
          {unit}
        </span>
      </div>
      <div className="chart-plot">
        <div className="chart-scale">
          <span>
            {maxY.toFixed(0)}
            {unit}
          </span>
          <span>
            {minY.toFixed(0)}
            {unit}
          </span>
        </div>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="chart-svg"
          style={{ height }}
          role="img"
        >
          <path d={linePath(series, minX, spanX, minY, spanY)} fill="none" stroke={COLORS[0]} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
    </div>
  )
}

export function MultiLineChart({
  title,
  series,
  yMin = 0,
  yMax,
  unit = '%',
  height = 88,
  emptyLabel = 'No data yet',
}: {
  title: string
  series: { label: string; points: Point[]; colorIndex?: number }[]
  yMin?: number
  yMax?: number
  unit?: string
  height?: number
  emptyLabel?: string
}) {
  const all = series.flatMap((s) => s.points)
  if (all.length === 0) {
    return (
      <div className="chart-block">
        <div className="chart-title">{title}</div>
        <p className="chart-empty">{emptyLabel}</p>
      </div>
    )
  }
  const minX = Math.min(...all.map((p) => p.x))
  const maxX = Math.max(...all.map((p) => p.x))
  const spanX = maxX - minX || 1
  const maxY = yMax ?? Math.max(yMin + 1, ...all.map((p) => p.y))
  const spanY = maxY - yMin || 1

  return (
    <div className="chart-block">
      <div className="chart-head">
        <span className="chart-title">{title}</span>
        <span className="chart-last">
          {yMin}
          {unit} – {maxY}
          {unit}
        </span>
      </div>
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
      <div className="chart-plot">
        <div className="chart-scale">
          <span>
            {maxY}
            {unit}
          </span>
          <span>
            {yMin}
            {unit}
          </span>
        </div>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="chart-svg"
          style={{ height }}
          role="img"
        >
          {series.map((s, i) =>
            s.points.length > 0 ? (
              <path
                key={s.label}
                d={linePath(s.points, minX, spanX, yMin, spanY)}
                fill="none"
                stroke={COLORS[s.colorIndex ?? i % COLORS.length]}
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
              />
            ) : null,
          )}
        </svg>
      </div>
    </div>
  )
}
