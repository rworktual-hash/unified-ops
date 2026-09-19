import type { VoiceMgExtra } from '../api'

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`
}

function fmtNum(value: number | null | undefined, digits = 1): string | null {
  if (value == null || Number.isNaN(value)) return null
  return value.toFixed(digits)
}

function rtpLabel(extra: VoiceMgExtra): string | null {
  const bits: string[] = []
  if (extra.rtp_sessions != null) bits.push(`${extra.rtp_sessions} sess`)
  const out = fmtNum(extra.rtp_mbps_out)
  const inn = fmtNum(extra.rtp_mbps_in)
  if (out != null || inn != null) {
    bits.push(`${out ?? '—'}↓/${inn ?? '—'}↑ Mbps`)
  }
  return bits.length ? bits.join(' · ') : null
}

function compactBits(extra: VoiceMgExtra): string[] {
  return [
    extra.cpu_pct != null ? `CPU ${fmtPct(extra.cpu_pct)}` : null,
    extra.load1 != null ? `load ${extra.load1.toFixed(2)}` : null,
    extra.mem ? `mem ${extra.mem}` : null,
    extra.active_calls != null ? `calls ${extra.active_calls}` : null,
    extra.mos != null ? `MOS ${extra.mos.toFixed(2)}` : null,
    extra.stall != null ? `stall ${extra.stall}` : null,
    rtpLabel(extra) ? `RTP ${rtpLabel(extra)}` : null,
    extra.jitter_ms != null ? `jitter ${fmtNum(extra.jitter_ms)}ms` : null,
  ].filter((bit): bit is string => Boolean(bit))
}

type Props = {
  extra: VoiceMgExtra
  compact?: boolean
}

export function VoiceMgExtras({ extra, compact = false }: Props) {
  const tiles = extraTiles(extra)
  if (compact) {
    const bits = compactBits(extra)
    return (
      <span className="ai-extra-line" title={bits.join(' · ')}>
        {bits.length ? <span className="muted bv-sub">{bits.join(' · ')}</span> : '—'}
      </span>
    )
  }

  return (
    <div className="ai-extra-block">
      <div className="ai-extra-head">
        <span className="metric-label">VoiceMG extras</span>
        {extra.role || extra.product ? (
          <span className="bv-pill bv-pill--ok">
            {[extra.product, extra.role].filter(Boolean).join(' · ')}
          </span>
        ) : null}
      </div>
      <div className="metric-grid gpu-metrics">
        {tiles.map((tile) => (
          <div className="metric-tile" key={tile.key}>
            <span className="metric-label">{tile.label}</span>
            <span className="metric-value">{tile.value}</span>
          </div>
        ))}
      </div>
      {extra.recorded_at ? (
        <p className="muted bv-sub">Portal {new Date(extra.recorded_at).toLocaleString()}</p>
      ) : null}
    </div>
  )
}

function extraTiles(extra: VoiceMgExtra): { key: string; label: string; value: string }[] {
  const tiles: { key: string; label: string; value: string }[] = []
  if (extra.cpu_pct != null) {
    tiles.push({ key: 'cpu', label: 'CPU', value: fmtPct(extra.cpu_pct) })
  }
  if (extra.load1 != null) {
    tiles.push({ key: 'load', label: 'Load', value: extra.load1.toFixed(2) })
  }
  if (extra.mem) {
    tiles.push({ key: 'mem', label: 'Memory', value: extra.mem })
  }
  if (extra.active_calls != null) {
    tiles.push({ key: 'calls', label: 'Active calls', value: String(extra.active_calls) })
  }
  if (extra.rtp_sessions != null) {
    tiles.push({ key: 'rtp', label: 'RTP sessions', value: String(extra.rtp_sessions) })
  }
  if (extra.rtp_mbps_out != null || extra.rtp_mbps_in != null) {
    tiles.push({
      key: 'rtp_mbps',
      label: 'RTP Mbps',
      value: `${fmtNum(extra.rtp_mbps_out) ?? '—'} out / ${fmtNum(extra.rtp_mbps_in) ?? '—'} in`,
    })
  }
  if (extra.jitter_ms != null) {
    tiles.push({ key: 'jitter', label: 'Jitter', value: `${fmtNum(extra.jitter_ms)} ms` })
  }
  if (extra.pkts_lost_delta != null) {
    tiles.push({ key: 'lost', label: 'Pkts lost', value: String(extra.pkts_lost_delta) })
  }
  if (extra.disk_used_pct != null) {
    tiles.push({
      key: 'disk',
      label: extra.disk_mount ? `Disk ${extra.disk_mount}` : 'Disk',
      value: fmtPct(extra.disk_used_pct),
    })
  }
  return tiles
}
