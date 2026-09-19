import { useCallback, useEffect, useState } from 'react'
import {
  fetchVoiceMgHistory,
  type VoiceMgHistory,
  type VoiceMgHistoryGroup,
  type VoiceMgHistoryPoint,
  type VoiceMgHistoryRange,
} from '../api'
import { LIVE_EXTRAS_INTERVAL_MS, useLivePoll } from '../useLivePoll'
import { SimpleLineChart } from './SimpleLineChart'

const TODAY_POLL_MS = 30_000
const EMPTY = 'No rows in this window on MariaDB voicemg.'

function series(
  points: VoiceMgHistoryPoint[],
  key: keyof Omit<VoiceMgHistoryPoint, 'ts'>,
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
  range: VoiceMgHistoryRange
  group: VoiceMgHistoryGroup
}

export function VoiceMgHistory({ range, group }: Props) {
  const [data, setData] = useState<VoiceMgHistory | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const next = await fetchVoiceMgHistory(range, group)
      setData(next)
    } catch (err) {
      setData((prev) =>
        prev
          ? prev
          : {
              ok: false,
              reason: err instanceof Error ? err.message : 'Failed to load VoiceMG history',
              range,
              group,
              since: null,
              bucket_seconds: range === '5m' ? 10 : 60,
              host_count: 0,
              point_count: 0,
              points: [],
            },
      )
    } finally {
      if (!silent) setLoading(false)
    }
  }, [group, range])

  useEffect(() => {
    void load()
  }, [load])

  const poll = useCallback(async () => {
    await load(true)
  }, [load])
  useLivePoll(poll, true, range === '5m' ? LIVE_EXTRAS_INTERVAL_MS : TODAY_POLL_MS)

  const points = data?.ok ? data.points : []

  return (
    <div className="vmg-history">
      <p className="muted">
        Live SELECT from <code>metrics_calls</code> + <code>metrics_system</code>
        {data?.ok
          ? ` · ${data.point_count} buckets · ${data.host_count} hosts · ${range === '5m' ? 'last 5 minutes' : 'today'}`
          : ''}
        {loading ? ' · loading…' : ''}
      </p>
      {data && !data.ok ? <p className="banner error">{data.reason}</p> : null}
      <div className="charts-grid">
        <SimpleLineChart
          title="Active calls"
          points={series(points, 'active_calls')}
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="MOS"
          points={series(points, 'mos')}
          yMin={1}
          yMax={4.5}
          unit=""
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="Jitter ms"
          points={series(points, 'jitter_ms')}
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="Packet loss %"
          points={series(points, 'packet_loss_pct')}
          yMin={0}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="RTP Mbps"
          points={series(points, 'rtp_mbps')}
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="CPU %"
          points={series(points, 'cpu_pct')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
      </div>
    </div>
  )
}
