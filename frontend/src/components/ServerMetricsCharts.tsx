import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchServerMetricsHistory, type ServerMetricsHistory } from '../api'
import { MultiLineChart, SimpleLineChart, buildSeriesFromValues } from './SimpleLineChart'

type Props = {
  serverId: number
  serverName: string
  isGpu: boolean
  defaultOpen?: boolean
  chartHeight?: number
}

function indexByTime<T extends { collected_at: string }>(rows: T[]): Map<string, number> {
  const times = [...new Set(rows.map((row) => row.collected_at))].sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime(),
  )
  const map = new Map<string, number>()
  times.forEach((time, index) => map.set(time, index))
  return map
}

export function ServerMetricsCharts({
  serverId,
  serverName,
  isGpu,
  defaultOpen = false,
  chartHeight = 72,
}: Props) {
  const [hours, setHours] = useState(defaultOpen ? 6 : 1)
  const [open, setOpen] = useState(defaultOpen)
  const [data, setData] = useState<ServerMetricsHistory | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      setData(await fetchServerMetricsHistory(serverId, hours))
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed to load history')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [serverId, hours])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  const hostSeries = useMemo(() => {
    if (!data?.host.length) return null
    const host = [...data.host].sort(
      (a, b) => new Date(a.collected_at).getTime() - new Date(b.collected_at).getTime(),
    )
    return {
      load: buildSeriesFromValues(host.map((h) => h.load_1m)),
      mem: buildSeriesFromValues(host.map((h) => h.mem_used_pct)),
      disk: buildSeriesFromValues(host.map((h) => h.disk_root_pct)),
    }
  }, [data])

  const gpuUtilSeries = useMemo(() => {
    if (!data?.gpu.length) return []
    const timeIndex = indexByTime(data.gpu)
    const byGpu = new Map<number, typeof data.gpu>()
    for (const g of data.gpu) {
      const list = byGpu.get(g.gpu_index) ?? []
      list.push(g)
      byGpu.set(g.gpu_index, list)
    }
    return [...byGpu.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([idx, rows]) => ({
        label: `GPU ${idx}`,
        colorIndex: idx,
        points: rows
          .map((r) => {
            const xi = timeIndex.get(r.collected_at)
            if (xi == null || r.utilization_pct == null) return null
            return { x: xi, y: r.utilization_pct }
          })
          .filter((p): p is { x: number; y: number } => p != null),
      }))
  }, [data])

  const gpuVramSeries = useMemo(() => {
    if (!data?.gpu.length) return []
    const timeIndex = indexByTime(data.gpu)
    const byGpu = new Map<number, typeof data.gpu>()
    for (const g of data.gpu) {
      const list = byGpu.get(g.gpu_index) ?? []
      list.push(g)
      byGpu.set(g.gpu_index, list)
    }
    return [...byGpu.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([idx, rows]) => ({
        label: `GPU ${idx}`,
        colorIndex: idx,
        points: rows
          .map((r) => {
            const xi = timeIndex.get(r.collected_at)
            const pct = r.mem_used_pct ?? (r.mem_used_mb && r.mem_total_mb ? (r.mem_used_mb / r.mem_total_mb) * 100 : null)
            if (xi == null || pct == null) return null
            return { x: xi, y: pct }
          })
          .filter((p): p is { x: number; y: number } => p != null),
      }))
  }, [data])

  const insightSeries = useMemo(() => {
    if (!data?.gpu_insights.length) return null
    const rows = [...data.gpu_insights].sort(
      (a, b) => new Date(a.collected_at).getTime() - new Date(b.collected_at).getTime(),
    )
    return {
      cpu: buildSeriesFromValues(rows.map((r) => r.cpu_util_pct)),
      gpuUtil: buildSeriesFromValues(rows.map((r) => r.gpu_util_avg)),
      gpuTemp: buildSeriesFromValues(rows.map((r) => r.gpu_temp_avg)),
    }
  }, [data])

  return (
    <div className={`server-charts-wrap${defaultOpen ? ' server-charts-wrap--open' : ''}`}>
      {defaultOpen ? null : (
        <button type="button" className="btn ghost chart-toggle" onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide charts' : 'Metrics history'}
        </button>
      )}
      {open ? (
        <div className="server-charts-panel">
          <div className="chart-toolbar">
            <span className="muted">{serverName} · last {hours}h</span>
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              aria-label="History range"
            >
              <option value={1}>1 hour</option>
              <option value={6}>6 hours</option>
              <option value={24}>24 hours</option>
            </select>
            <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
              {loading ? 'Loading…' : 'Refresh'}
            </button>
          </div>
          {err ? <p className="ssh-line fail">{err}</p> : null}
          <div className="charts-grid">
            {hostSeries ? (
              <>
                <SimpleLineChart title="CPU load (1m)" points={hostSeries.load} unit="" height={chartHeight} />
                <SimpleLineChart title="Memory" points={hostSeries.mem} unit="%" yMin={0} yMax={100} height={chartHeight} />
                <SimpleLineChart title="Disk /" points={hostSeries.disk} unit="%" yMin={0} yMax={100} height={chartHeight} />
              </>
            ) : null}
            {insightSeries?.cpu.length ? (
              <SimpleLineChart title="CPU util" points={insightSeries.cpu} unit="%" yMin={0} yMax={100} height={chartHeight} />
            ) : null}
            {isGpu && gpuUtilSeries.some((s) => s.points.length > 0) ? (
              <MultiLineChart title="Per-GPU util" series={gpuUtilSeries} yMin={0} yMax={100} unit="%" height={chartHeight} />
            ) : null}
            {isGpu && gpuVramSeries.some((s) => s.points.length > 0) ? (
              <MultiLineChart title="Per-GPU VRAM" series={gpuVramSeries} yMin={0} yMax={100} unit="%" height={chartHeight} />
            ) : null}
            {insightSeries?.gpuTemp.length ? (
              <SimpleLineChart title="GPU temp avg" points={insightSeries.gpuTemp} unit="°C" height={chartHeight} />
            ) : null}
          </div>
          {!loading && !err && !data?.host.length && !data?.gpu.length ? (
            <p className="muted">No history in this range. Enable scheduled collect or click Collect metrics a few times.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
