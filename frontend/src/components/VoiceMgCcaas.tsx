import { useMemo, useState } from 'react'
import type { VoiceMgExtra } from '../api'

type FilterId = 'all' | 'ai_ccaas' | 'ccaas'

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
  const rows = useMemo(() => {
    if (filter === 'all') return servers
    return servers.filter((row) => (row.group || 'ccaas') === filter)
  }, [filter, servers])
  const vmg = rows.filter((row) => (row.role || row.hostname).toLowerCase().includes('stt') === false)
  const stt = rows.filter((row) => (row.role || row.hostname).toLowerCase().includes('stt'))
  const kpis = {
    calls: sum(rows.map((r) => r.active_calls)),
    stall: sum(rows.map((r) => r.stall ?? r.udp_inactive)),
    mos: avg(rows.map((r) => r.mos)),
    jitter: avg(rows.map((r) => r.jitter_ms)),
    loss: avg(rows.map((r) => r.packet_loss_pct)),
    rtp: sum(rows.map((r) => rtpMbps(r))),
    cpu: avg(rows.map((r) => r.cpu_pct)),
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Live CCaaS / AI-CCaaS</h2>
          <p className="muted">Latest MariaDB <code>voicemg</code> row per host — same live numbers as voicemg.worktual.tech.</p>
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
            <HostMini key={row.id} row={row} />
          ))}
          {!vmg.length ? <p className="muted">No VoiceMG hosts in this filter.</p> : null}
        </div>
        <div>
          <p className="metric-label">STT</p>
          {stt.map((row) => (
            <HostMini key={row.id} row={row} />
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
      </div>

      <div className="vmg-ccaas-cards">
        {rows.map((row) => (
          <HostCard key={row.id} row={row} />
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

function HostMini({ row }: { row: VoiceMgExtra }) {
  return (
    <div className="vmg-ccaas-mini">
      <strong>{row.hostname}</strong>
      <span className="muted">
        {row.active_calls ?? 0} calls
        {row.stall != null ? ` · ${row.stall} stall` : ''}
        {row.mos != null ? ` · ${fmt(row.mos, 2)} MOS` : ' · MOS n/a'}
        {qualityBadge(row) ? ` · ${qualityBadge(row)}` : ''}
      </span>
    </div>
  )
}

function HostCard({ row }: { row: VoiceMgExtra }) {
  const rtp = rtpMbps(row)
  return (
    <article className="vmg-ccaas-card">
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
      </p>
    </article>
  )
}
