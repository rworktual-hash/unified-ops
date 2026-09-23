import { useMemo, useState } from 'react'
import type { VoiceMgExtra, VoiceMgHistoryGroup, VoiceMgHistoryRange } from '../api'
import { VoiceMgHistory } from './VoiceMgHistory'

type FilterId = VoiceMgHistoryGroup

const HISTORY_RANGES: Array<[VoiceMgHistoryRange, string]> = [
  ['live', 'Live'],
  ['5m', '5m'],
  ['30m', '30m'],
  ['1h', '1h'],
  ['2h', '2h'],
  ['6h', '6h'],
  ['12h', '12h'],
  ['today', 'Today'],
  ['yesterday', 'Yesterday'],
  ['2d', '2 days'],
  ['week', 'Week'],
  ['custom', 'Range…'],
]

function localInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function avg(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((v): v is number => v != null && !Number.isNaN(v))
  if (!nums.length) return null
  return nums.reduce((sum, n) => sum + n, 0) / nums.length
}

function sum(values: Array<number | null | undefined>): number {
  return values.reduce<number>((total, n) => total + (n ?? 0), 0)
}

function fmt(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

function rtpMbps(row: VoiceMgExtra): number | null {
  if (row.rtp_mbps_out == null && row.rtp_mbps_in == null) return null
  return (row.rtp_mbps_out ?? 0) + (row.rtp_mbps_in ?? 0)
}

function qualityBadge(row: VoiceMgExtra): string | null {
  const raw = (row.quality_source || row.rtcp || '').toLowerCase()
  if (!raw) return null
  if (raw.includes('rtcp')) return 'RTCP'
  if (raw.includes('estim')) return 'ESTIMATE'
  return raw.toUpperCase()
}

function mosLabel(value: number | null | undefined): string {
  if (value == null) return 'n/a'
  if (value >= 4.0) return 'excellent'
  if (value >= 3.6) return 'good'
  if (value >= 3.1) return 'fair'
  return 'poor'
}

type Props = {
  servers: VoiceMgExtra[]
  loading?: boolean
}

export function VoiceMgCcaas({ servers, loading = false }: Props) {
  const [filter, setFilter] = useState<FilterId>('ai_ccaas')
  const [range, setRange] = useState<VoiceMgHistoryRange>('5m')
  const [selectedHostId, setSelectedHostId] = useState<number | null>(null)
  const [customStart, setCustomStart] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 1)
    d.setHours(0, 0, 0, 0)
    return localInputValue(d)
  })
  const [customEnd, setCustomEnd] = useState(() => localInputValue(new Date()))
  const rows = useMemo(() => {
    if (filter === 'all') return servers
    return servers.filter((row) => (row.group || 'ccaas') === filter)
  }, [filter, servers])
  const selected = rows.find((row) => row.id === selectedHostId) ?? null
  const scoped = selected ? [selected] : rows
  const kpis = {
    calls: sum(scoped.map((r) => r.active_calls)),
    stall: sum(scoped.map((r) => r.stall ?? r.udp_inactive)),
    mos: avg(scoped.map((r) => r.mos)),
    jitter: avg(scoped.map((r) => r.jitter_ms)),
    loss: avg(scoped.map((r) => r.packet_loss_pct)),
    rtp: sum(scoped.map((r) => rtpMbps(r))),
    cpu: avg(scoped.map((r) => r.cpu_pct)),
    disk: avg(scoped.map((r) => r.disk_used_pct)),
    udp: sum(scoped.map((r) => r.udp_sockets ?? r.udp_active)),
    rtpGb: sum(scoped.map((r) => r.rtp_gb)),
  }
  const toggleHost = (id: number) => {
    setSelectedHostId((prev) => (prev === id ? null : id))
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Calls</h2>
          <p className="muted">
            {rows.length} hosts · {kpis.calls} calls
            {kpis.mos != null ? ` · MOS ${fmt(kpis.mos, 2)}` : ''}
            {selected ? ` · ${selected.hostname}` : ''}
          </p>
        </div>
        <div className="bv-tabs">
          {(
            [
              ['ai_ccaas', 'AI-CCaaS'],
              ['ccaas', 'CCaaS'],
              ['all', 'All'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`bv-tab ${filter === id ? 'active' : ''}`}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && !servers.length ? <p className="muted">Loading live portal metrics…</p> : null}

      <div className="stat-row backupvault-stat-row">
        <Kpi label="Active calls" value={String(kpis.calls)} />
        <Kpi
          label="MOS"
          value={kpis.mos == null ? '—' : fmt(kpis.mos, 2)}
          hint={kpis.mos == null ? undefined : mosLabel(kpis.mos)}
          tone={mosTone(kpis.mos)}
        />
        <Kpi label="Jitter" value={kpis.jitter == null ? '—' : `${fmt(kpis.jitter, 1)} ms`} />
        <Kpi label="Packet loss" value={kpis.loss == null ? '—' : `${fmt(kpis.loss, 2)}%`} />
        <Kpi label="Stalled" value={String(kpis.stall)} tone={kpis.stall > 0 ? 'warn' : undefined} />
        <Kpi label="RTP" value={kpis.rtp == null ? '—' : `${fmt(kpis.rtp, 1)} Mbps`} />
      </div>
      <div className="stat-row backupvault-stat-row">
        <Kpi label="CPU" value={kpis.cpu == null ? '—' : `${fmt(kpis.cpu, 0)}%`} />
        <Kpi label="Disk" value={kpis.disk == null ? '—' : `${fmt(kpis.disk, 0)}%`} />
        <Kpi label="UDP sockets" value={String(kpis.udp)} />
        <Kpi label="RTP volume" value={kpis.rtpGb == null ? '—' : `${fmt(kpis.rtpGb, 2)} GB`} />
      </div>

      <div className="table-wrap vmg-host-table">
        <table>
          <thead>
            <tr>
              <th>Host</th>
              <th>Calls</th>
              <th>MOS</th>
              <th>Jitter</th>
              <th>Loss</th>
              <th>RTP</th>
              <th>Disk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={selectedHostId === row.id ? 'vmg-host-row--selected' : undefined}
                onClick={() => toggleHost(row.id)}
              >
                <td>
                  <strong>{row.hostname}</strong>
                  <div className="muted bv-sub">{hostRole(row)}</div>
                </td>
                <td>{row.active_calls ?? 0}</td>
                <td className={mosTone(row.mos) === 'ok' ? 'email-status-ok' : mosTone(row.mos) === 'warn' ? 'email-status-warn' : undefined}>
                  {row.mos == null ? '—' : fmt(row.mos, 2)}
                </td>
                <td>{row.jitter_ms == null ? '—' : `${fmt(row.jitter_ms, 1)} ms`}</td>
                <td>{row.packet_loss_pct == null ? '—' : `${fmt(row.packet_loss_pct, 2)}%`}</td>
                <td>{rtpMbps(row) == null ? '—' : `${fmt(rtpMbps(row), 1)}`}</td>
                <td>{row.disk_used_pct == null ? '—' : `${fmt(row.disk_used_pct, 0)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <p className="muted">No hosts in this group.</p> : null}
      </div>

      <div className="chart-toolbar vmg-range-toolbar">
        <span className="muted">{selected ? selected.hostname : 'All hosts'}</span>
        <div className="bv-tabs">
          {HISTORY_RANGES.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`bv-tab ${range === id ? 'active' : ''}`}
              onClick={() => setRange(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {range === 'custom' ? (
        <div className="vmg-custom-range">
          <label>
            From
            <input
              type="datetime-local"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
            />
          </label>
          <label>
            To
            <input
              type="datetime-local"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
            />
          </label>
        </div>
      ) : null}
      <VoiceMgHistory
        range={range}
        group={filter}
        start={range === 'custom' ? customStart : undefined}
        end={range === 'custom' ? customEnd : undefined}
        serverId={selected?.id ?? null}
        hostName={selected?.hostname ?? null}
      />
    </section>
  )
}

function mosTone(value: number | null | undefined): 'ok' | 'warn' | undefined {
  if (value == null) return undefined
  if (value >= 3.6) return 'ok'
  return 'warn'
}

function hostRole(row: VoiceMgExtra): string {
  const role = (row.role || (row.hostname.toLowerCase().includes('stt') ? 'stt' : 'vmg')).toUpperCase()
  const quality = qualityBadge(row)
  return quality ? `${role} · ${quality}` : role
}

function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint?: string
  tone?: 'ok' | 'warn'
}) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className={`stat-value${tone ? ` ${tone}` : ''}`}>{value}</span>
      {hint ? <span className="muted bv-sub">{hint}</span> : null}
    </div>
  )
}
