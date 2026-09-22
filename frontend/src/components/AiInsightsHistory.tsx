import { useCallback, useEffect, useState } from 'react'
import {
  fetchAiInsightHistory,
  type AiInsightHistory,
  type AiInsightHistoryPoint,
  type AiInsightHistoryRange,
} from '../api'
import { LIVE_EXTRAS_INTERVAL_MS, useLivePoll } from '../useLivePoll'
import { SimpleLineChart } from './SimpleLineChart'

const FAST_POLL = new Set<AiInsightHistoryRange>(['30m', '60m', '1h'])
const RANGE_LABEL: Record<string, string> = {
  '30m': 'last 30 minutes',
  '60m': 'last 60 minutes',
  '1h': 'last hour',
  '2h': 'last 2 hours',
  today: 'today',
}
const EMPTY = 'No rows in this window on MariaDB ai_insights_platform.'

function series(
  points: AiInsightHistoryPoint[],
  key: keyof Omit<AiInsightHistoryPoint, 'ts'>,
): { x: number; y: number }[] {
  return points
    .map((point) => {
      const y = point[key]
      if (y == null || Number.isNaN(y)) return null
      return { x: new Date(point.ts).getTime(), y }
    })
    .filter((p): p is { x: number; y: number } => p != null)
}

type Props = {
  range: AiInsightHistoryRange
  group: string
  serverId?: number | null
  hostName?: string | null
}

export function AiInsightsHistory({ range, group, serverId, hostName }: Props) {
  const [data, setData] = useState<AiInsightHistory | null>(null)
  const [loading, setLoading] = useState(true)
  const queryRange: AiInsightHistoryRange = range === '1h' ? '60m' : range

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true)
      try {
        const next = await fetchAiInsightHistory(queryRange, group, serverId)
        setData(next)
      } catch (err) {
        setData((prev) =>
          prev
            ? prev
            : {
                ok: false,
                reason: err instanceof Error ? err.message : 'Failed to load AI Insights history',
                range: queryRange,
                group,
                since: null,
                until: null,
                bucket_seconds: 60,
                host_count: 0,
                point_count: 0,
                points: [],
              },
        )
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [group, queryRange, serverId],
  )

  useEffect(() => {
    void load()
  }, [load])

  const poll = useCallback(async () => {
    await load(true)
  }, [load])
  useLivePoll(poll, true, FAST_POLL.has(range) ? LIVE_EXTRAS_INTERVAL_MS : 30_000)

  const points = data?.ok ? data.points : []
  const scope = hostName || data?.host_name || (serverId != null ? `host #${serverId}` : 'fleet average')
  const showGpu =
    series(points, 'gpu_utilization').length > 0 || series(points, 'gpu_temperature').length > 0

  return (
    <div className="vmg-history ai-history">
      <p className="muted">
        Live SELECT from <code>ai_insights_platform</code>
        {data?.source_table ? ` · ${data.source_table}` : ''}
        {data?.ok
          ? ` · ${data.point_count} buckets · ${data.host_count} hosts · ${scope} · ${RANGE_LABEL[range] || range}`
          : ''}
        {loading ? ' · loading…' : ''}
      </p>
      {data && !data.ok ? <p className="banner error">{data.reason}</p> : null}
      <div className="charts-grid">
        <SimpleLineChart
          title="CPU %"
          points={series(points, 'cpu_utilization')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="RAM %"
          points={series(points, 'memory_utilization')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="Disk %"
          points={series(points, 'storage_utilization')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart title="Load average" points={series(points, 'load_average')} yMin={0} emptyLabel={EMPTY} />
        {showGpu ? (
          <>
            <SimpleLineChart
              title="GPU %"
              points={series(points, 'gpu_utilization')}
              yMin={0}
              yMax={100}
              unit="%"
              emptyLabel={EMPTY}
            />
            <SimpleLineChart
              title="GPU temp"
              points={series(points, 'gpu_temperature')}
              yMin={0}
              unit="°C"
              emptyLabel={EMPTY}
            />
          </>
        ) : null}
      </div>
    </div>
  )
}
