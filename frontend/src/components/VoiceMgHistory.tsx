import { useCallback, useEffect, useState } from 'react'
import {
  fetchVoiceMgHistory,
  type VoiceMgHistory,
  type VoiceMgHistoryGroup,
  type VoiceMgHistoryPoint,
  type VoiceMgHistoryRange,
} from '../api'
import { LIVE_EXTRAS_INTERVAL_MS, useLivePoll } from '../useLivePoll'
import { MultiLineChart, SimpleLineChart } from './SimpleLineChart'

const FAST_POLL = new Set<VoiceMgHistoryRange>(['live', '5m', '30m', '1h'])
const SLOW_POLL = new Set<VoiceMgHistoryRange>(['today', '2h'])
const RANGE_LABEL: Record<string, string> = {
  live: 'live (last 5 minutes)',
  '5m': 'last 5 minutes',
  '30m': 'last 30 minutes',
  '1h': 'last hour',
  '2h': 'last 2 hours',
  '6h': 'last 6 hours',
  '12h': 'last 12 hours',
  today: 'today',
  yesterday: 'yesterday',
  '2d': 'last 2 days',
  week: 'last week',
  custom: 'custom range',
}
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
  start?: string
  end?: string
  serverId?: number | null
  hostName?: string | null
}

export function VoiceMgHistory({ range, group, start, end, serverId, hostName }: Props) {
  const [data, setData] = useState<VoiceMgHistory | null>(null)
  const [loading, setLoading] = useState(true)
  const queryRange: VoiceMgHistoryRange = range === 'live' ? '5m' : range

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true)
      try {
        const next = await fetchVoiceMgHistory(queryRange, group, start, end, serverId)
        setData(next)
      } catch (err) {
        setData((prev) =>
          prev
            ? prev
            : {
                ok: false,
                reason: err instanceof Error ? err.message : 'Failed to load VoiceMG history',
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
    [end, group, queryRange, serverId, start],
  )

  useEffect(() => {
    void load()
  }, [load])

  const poll = useCallback(async () => {
    await load(true)
  }, [load])
  useLivePoll(
    poll,
    FAST_POLL.has(range) || SLOW_POLL.has(range),
    FAST_POLL.has(range) ? LIVE_EXTRAS_INTERVAL_MS : 30_000,
  )

  const points = data?.ok ? data.points : []
  const scope = hostName || data?.host_name || (serverId != null ? `host #${serverId}` : 'fleet')

  return (
    <div className="vmg-history">
      <p className="muted">
        Live SELECT from <code>voicemg</code> utilization tables
        {data?.ok
          ? ` · ${data.point_count} buckets · ${data.host_count} hosts · ${scope} · ${RANGE_LABEL[range] || range}`
          : ''}
        {loading ? ' · loading…' : ''}
      </p>
      {data && !data.ok ? <p className="banner error">{data.reason}</p> : null}
      <div className="charts-grid">
        <SimpleLineChart title="Active calls" points={series(points, 'active_calls')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="MOS" points={series(points, 'mos')} yMin={1} yMax={4.5} emptyLabel={EMPTY} />
        <SimpleLineChart title="Jitter ms" points={series(points, 'jitter_ms')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart
          title="Packet loss %"
          points={series(points, 'packet_loss_pct')}
          yMin={0}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart title="RTP Mbps" points={series(points, 'rtp_mbps')} yMin={0} emptyLabel={EMPTY} />
        <MultiLineChart
          title="RTP vs expected G.711"
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
          series={[
            { label: 'RTP Mbps', points: series(points, 'rtp_mbps') },
            { label: 'Expected', points: series(points, 'rtp_mbps_exp'), colorIndex: 2 },
          ]}
        />
        <SimpleLineChart title="CPU %" points={series(points, 'cpu_pct')} yMin={0} yMax={100} unit="%" emptyLabel={EMPTY} />
        <SimpleLineChart title="MEM %" points={series(points, 'mem_pct')} yMin={0} yMax={100} unit="%" emptyLabel={EMPTY} />
        <SimpleLineChart title="RX errors" points={series(points, 'rx_errors')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="RX drops" points={series(points, 'rx_drops')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="Open FDs" points={series(points, 'open_fds')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="Threads" points={series(points, 'threads')} yMin={0} emptyLabel={EMPTY} />
        <MultiLineChart
          title="Inter-server messages"
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
          series={[
            { label: 'Sent/s', points: series(points, 'ipc_sent_ps') },
            { label: 'Recv/s', points: series(points, 'ipc_recv_ps'), colorIndex: 1 },
          ]}
        />
        <SimpleLineChart
          title="Inter-server latency ms"
          points={series(points, 'ipc_latency_ms')}
          yMin={0}
          emptyLabel={EMPTY}
        />
        <SimpleLineChart title="Runqueue" points={series(points, 'runqueue')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="Buffers MB" points={series(points, 'buffers_mb')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="Cached MB" points={series(points, 'cached_mb')} yMin={0} emptyLabel={EMPTY} />
        <MultiLineChart
          title="UDP packets/s"
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
          series={[
            { label: 'In', points: series(points, 'udp_pps_in') },
            { label: 'Out', points: series(points, 'udp_pps_out'), colorIndex: 1 },
          ]}
        />
        <MultiLineChart
          title="NIC RX / TX"
          yMin={0}
          unit=""
          emptyLabel={EMPTY}
          series={[
            { label: 'RX Mbps', points: series(points, 'nic_rx_mbps') },
            { label: 'TX Mbps', points: series(points, 'nic_tx_mbps'), colorIndex: 1 },
          ]}
        />
        <SimpleLineChart
          title="Gateway process CPU %"
          points={series(points, 'proc_cpu_pct')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart
          title="Gateway process MEM %"
          points={series(points, 'proc_mem_pct')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
        <SimpleLineChart title="UDP sockets" points={series(points, 'udp_sockets')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart title="RTP GB total" points={series(points, 'rtp_gb')} yMin={0} emptyLabel={EMPTY} />
        <SimpleLineChart
          title="Disk used %"
          points={series(points, 'disk_used_pct')}
          yMin={0}
          yMax={100}
          unit="%"
          emptyLabel={EMPTY}
        />
      </div>
    </div>
  )
}
