import { useMemo, useState } from 'react'
import type { VoiceMgExtra, VoiceMgHistoryGroup, VoiceMgHistoryRange } from '../api'
import { SimpleBarChart } from './SimpleBarChart'
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
  const vmg = rows.filter((row) => (row.role || row.hostname).toLowerCase().includes('stt') === false)
  const stt = rows.filter((row) => (row.role || row.hostname).toLowerCase().includes('stt'))
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
  const productBars = useMemo(() => {
    const byProduct = new Map<string, number>()
    for (const row of scoped) {
      const key = row.product || row.group || 'unknown'
      byProduct.set(key, (byProduct.get(key) ?? 0) + (row.active_calls ?? 0))
    }
    return [...byProduct.entries()].map(([label, value]) => ({ label, value }))
  }, [scoped])
  const diskBars = scoped.map((row) => ({
    label: row.hostname,
    value: row.disk_used_pct,
  }))

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Live CCaaS / AI-CCaaS</h2>
          <p className="muted">Live portal metrics. Click a host for its series.</p>
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

      <div className="vmg-ccaas-grid">
        <div>
          <p className="metric-label">VoiceMG</p>
          {vmg.map((row) => (
            <HostMini
              key={row.id}
              row={row}
              selected={selectedHostId === row.id}
              onSelect={() => toggleHost(row.id)}
            />
          ))}
          {!vmg.length ? <p className="muted">No VoiceMG hosts in this filter.</p> : null}
        </div>
        <div>
          <p className="metric-label">STT</p>
          {stt.map((row) => (
            <HostMini
              key={row.id}
              row={row}
              selected={selectedHostId === row.id}
              onSelect={() => toggleHost(row.id)}
            />
          ))}
          {!stt.length ? <p className="muted">No STT hosts in this filter.</p> : null}
        </div>
      </div>

      <div className="stat-row backupvault-stat-row">
        <Kpi label="Active calls" value={String(kpis.calls)} />
        <Kpi label="Stalled UDP" value={String(kpis.stall)} />
        <Kpi
          label="MOS (1–4.5)"
          value={kpis.mos == null ? '—' : fmt(kpis.mos, 2)}
          hint={kpis.mos == null ? undefined : mosLabel(kpis.mos)}
        />
        <Kpi label="Jitter ms" value={fmt(kpis.jitter, 1)} />
        <Kpi label="Packet loss %" value={kpis.loss == null ? '—' : `${fmt(kpis.loss, 2)}%`} />
        <Kpi label="RTP Mbps" value={fmt(kpis.rtp, 1)} />
        <Kpi label="Avg CPU %" value={kpis.cpu == null ? '—' : `${fmt(kpis.cpu, 0)}%`} />
        <Kpi label="Disk %" value={kpis.disk == null ? '—' : `${fmt(kpis.disk, 0)}%`} />
        <Kpi label="UDP sockets" value={String(kpis.udp)} />
        <Kpi label="RTP GB" value={fmt(kpis.rtpGb, 2)} />
      </div>

      <div className="chart-toolbar vmg-range-toolbar">
        <span className="muted">History from MariaDB</span>
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
      {selected ? (
        <p className="muted">
          Showing {selected.hostname}. Click the host again for fleet view.
        </p>
      ) : (
        <p className="muted">Fleet view. Click a host card to switch its live charts.</p>
      )}
      <div className="charts-grid">
        <SimpleBarChart title="Disk % by server" rows={diskBars} unit="%" max={100} />
        <SimpleBarChart title="Calls by product" rows={productBars} unit="" />
      </div>
      <VoiceMgHistory
        range={range}
        group={filter}
        start={range === 'custom' ? customStart : undefined}
        end={range === 'custom' ? customEnd : undefined}
        serverId={selected?.id ?? null}
        hostName={selected?.hostname ?? null}
      />

      <div className="vmg-ccaas-cards">
        {rows.map((row) => (
          <HostCard
            key={row.id}
            row={row}
            selected={selectedHostId === row.id}
            onSelect={() => toggleHost(row.id)}
          />
        ))}
      </div>
    </section>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint ? <span className="muted bv-sub">{hint}</span> : null}
    </div>
  )
}

function HostMini({
  row,
  selected,
  onSelect,
}: {
  row: VoiceMgExtra
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`vmg-ccaas-mini${selected ? ' vmg-ccaas-mini--selected' : ''}`}
      onClick={onSelect}
    >
      <strong>{row.hostname}</strong>
      <span className="muted">
        {row.active_calls ?? 0} calls
        {row.stall != null ? ` · ${row.stall} stall` : ''}
        {row.mos != null ? ` · ${fmt(row.mos, 2)} MOS` : ' · MOS n/a'}
        {qualityBadge(row) ? ` · ${qualityBadge(row)}` : ''}
      </span>
    </button>
  )
}

function HostCard({
  row,
  selected,
  onSelect,
}: {
  row: VoiceMgExtra
  selected: boolean
  onSelect: () => void
}) {
  const rtp = rtpMbps(row)
  return (
    <article
      className={`vmg-ccaas-card${selected ? ' vmg-ccaas-card--selected' : ''}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
    >
      <div className="ai-extra-head">
        <strong>{row.hostname}</strong>
        <span className="bv-pill bv-pill--ok">
          {(row.role || (row.hostname.toLowerCase().includes('stt') ? 'stt' : 'vmg')).toUpperCase()}
          {qualityBadge(row) ? ` · ${qualityBadge(row)}` : ''}
        </span>
      </div>
      <p className="muted bv-sub">
        {row.active_calls ?? 0} calls
        {row.mos != null ? ` · ${fmt(row.mos, 2)} MOS` : ' · MOS n/a'}
        {row.jitter_ms != null ? ` · ${fmt(row.jitter_ms, 1)} ms jitter` : ''}
        {row.packet_loss_pct != null ? ` · ${fmt(row.packet_loss_pct, 2)}% loss` : ''}
      </p>
      <p className="muted bv-sub">
        {row.cpu_pct != null ? `CPU ${fmt(row.cpu_pct, 0)}%` : 'CPU —'}
        {row.mem_pct != null ? ` · MEM ${fmt(row.mem_pct, 0)}%` : row.mem ? ` · ${row.mem}` : ''}
      </p>
      <p className="muted bv-sub">
        UDP {row.udp_active ?? '—'} live
        {row.udp_inactive != null || row.stall != null
          ? ` · ${row.stall ?? row.udp_inactive} stall`
          : ''}
        {rtp != null ? ` · ${fmt(rtp, 1)} Mbps` : ''}
        {row.rtp_mbps_exp != null ? ` · exp ${fmt(row.rtp_mbps_exp, 1)}` : ''}
        {row.udp_sockets != null ? ` · ${row.udp_sockets} sockets` : ''}
      </p>
      <p className="muted bv-sub">
        {row.disk_used_pct != null ? `Disk ${fmt(row.disk_used_pct, 0)}%` : 'Disk —'}
        {row.open_fds != null ? ` · FDs ${row.open_fds}` : ''}
        {row.threads != null ? ` · thr ${row.threads}` : ''}
        {row.rx_errors != null ? ` · RX err ${fmt(row.rx_errors, 0)}` : ''}
        {row.nic_rx_mbps != null || row.nic_tx_mbps != null
          ? ` · NIC ${fmt(row.nic_rx_mbps, 1)}/${fmt(row.nic_tx_mbps, 1)}`
          : ''}
      </p>
    </article>
  )
}
