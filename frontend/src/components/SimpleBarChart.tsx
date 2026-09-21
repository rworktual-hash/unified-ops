type BarRow = { label: string; value: number | null | undefined }

type Props = {
  title: string
  rows: BarRow[]
  unit?: string
  max?: number
  emptyLabel?: string
}

export function SimpleBarChart({
  title,
  rows,
  unit = '%',
  max,
  emptyLabel = 'No rows in this window on MariaDB voicemg.',
}: Props) {
  const usable = rows.filter((row) => row.value != null && !Number.isNaN(row.value))
  const peak = max ?? Math.max(1, ...usable.map((row) => row.value as number))

  return (
    <div className="chart-block chart-block-wide">
      <div className="chart-title">{title}</div>
      {!usable.length ? (
        <p className="chart-empty">{emptyLabel}</p>
      ) : (
        <div className="vmg-bar-list">
          {usable.map((row) => {
            const value = row.value as number
            const width = Math.max(2, Math.min(100, (value / peak) * 100))
            const warn = unit === '%' && value >= 85
            return (
              <div key={row.label} className="vmg-bar-row">
                <span className="vmg-bar-label" title={row.label}>
                  {row.label}
                </span>
                <span className="vmg-bar-track">
                  <span
                    className={`vmg-bar-fill${warn ? ' vmg-bar-fill--warn' : ''}`}
                    style={{ width: `${width}%` }}
                  />
                </span>
                <span className="vmg-bar-value">
                  {value.toFixed(unit === '%' ? 0 : 1)}
                  {unit}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
