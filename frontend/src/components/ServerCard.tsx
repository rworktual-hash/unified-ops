import { healthLabel, healthScoreFromHost } from '../lib/healthScore'
import type { ConnectionTestResult, MetricsBundle, Server } from '../types'
import { MetricBar } from './MetricBar'

type Props = {
  server: Server
  metrics: MetricsBundle | null
  testResult: ConnectionTestResult | undefined
  testing: boolean
  collecting: boolean
  investigating: boolean
  onTest: () => void
  onCollect: () => void
  onInvestigate: () => void
  onRequestRecollect: () => void
}

export function ServerCard({
  server,
  metrics,
  testResult,
  testing,
  collecting,
  investigating,
  onTest,
  onCollect,
  onInvestigate,
  onRequestRecollect,
}: Props) {
  const host = metrics?.host[0]
  const isGpu = server.server_type === 'gpu' || server.project === 'ai'
  const gpus = metrics?.gpu.filter((g) => g.status === 'ok') ?? []
  const maxGpuUtil = gpus.length ? Math.max(...gpus.map((g) => g.utilization_pct ?? 0)) : null
  const health = healthScoreFromHost(host)
  const label = healthLabel(health)

  const loadDisplay = host?.load_1m != null ? host.load_1m.toFixed(2) : '—'
  const loadPct =
    host?.load_1m != null ? Math.min(100, (host.load_1m / 8) * 100) : null

  return (
    <article className="server-card">
      <div className="server-card-top">
        <div className="server-card-title-block">
          <p className="server-card-type">
            {(server.project ?? 'fleet').toUpperCase()} · {server.server_type ?? 'host'}
          </p>
          <h3>{server.server_name}</h3>
          <p className="server-card-meta">
            {server.ip_address}:{server.ssh_port}
          </p>
        </div>
        <div className={`health-badge ${label}`}>
          <span className="health-score">{health ?? '—'}</span>
          <span className="health-word">{label === 'unknown' ? 'no data' : label}</span>
        </div>
      </div>

      {server.is_active ? (
        <>
          <div className="metric-bars">
            <MetricBar
              label="CPU load"
              valuePct={loadPct}
              display={loadDisplay}
              warnAt={50}
              critAt={75}
            />
            <MetricBar
              label="Memory"
              valuePct={host?.mem_used_pct ?? null}
              display={host?.mem_used_pct != null ? `${host.mem_used_pct.toFixed(0)}%` : '—'}
            />
            <MetricBar
              label="Disk /"
              valuePct={host?.disk_root_pct ?? null}
              display={host?.disk_root_pct != null ? `${host.disk_root_pct.toFixed(0)}%` : '—'}
            />
          </div>

          {isGpu && (
            <div className="gpu-strip">
              <span>GPU</span>
              <strong>{maxGpuUtil != null ? `${maxGpuUtil.toFixed(0)}% util` : '—'}</strong>
              <span className="muted-inline">{gpus.length ? `${gpus.length} device(s)` : ''}</span>
            </div>
          )}

          {testResult && (
            <p className={`ssh-line ${testResult.success ? 'ok' : 'fail'}`}>
              SSH {testResult.success ? 'OK' : 'failed'}
              {testResult.latency_ms != null ? ` · ${testResult.latency_ms} ms` : ''}
            </p>
          )}

          <div className="server-actions compact">
            <button type="button" className="btn primary sm" disabled={collecting} onClick={onCollect}>
              {collecting ? 'Collecting…' : 'Collect'}
            </button>
            <button type="button" className="btn ghost sm" disabled={testing} onClick={onTest}>
              {testing ? '…' : 'Test SSH'}
            </button>
            <button type="button" className="btn ghost sm" disabled={investigating} onClick={onInvestigate}>
              Investigate
            </button>
            <button type="button" className="btn ghost sm" onClick={onRequestRecollect}>
              Recollect
            </button>
          </div>
        </>
      ) : (
        <p className="muted-block">Inactive — configure SSH access to monitor this host.</p>
      )}
    </article>
  )
}
