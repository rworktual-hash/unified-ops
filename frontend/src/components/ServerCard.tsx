import type { ConnectionTestResult, MetricsBundle, Server } from '../types'

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
  const gpus = metrics?.gpu.filter((g) => g.status === 'ok') ?? []
  const maxGpuUtil = gpus.length ? Math.max(...gpus.map((g) => g.utilization_pct ?? 0)) : null
  const maxTemp = gpus.length ? Math.max(...gpus.map((g) => g.temperature_c ?? 0)) : null

  return (
    <article className="server-card">
      <div className="server-card-head">
        <div>
          <p className="server-card-label">{server.project ?? 'ai'} · {server.server_type ?? 'gpu'}</p>
          <h3>{server.server_name}</h3>
          <p className="server-card-meta">
            {server.ip_address}:{server.ssh_port} · {server.ssh_username}
            {server.ssh_auth_mode !== 'key' ? ` · auth ${server.ssh_auth_mode}` : ''}
          </p>
        </div>
        <span className={`status-pill ${server.is_active ? 'live' : 'off'}`}>
          {server.is_active ? 'Active' : 'Inactive'}
        </span>
      </div>

      {server.is_active ? (
        <>
          <div className="metric-grid">
            <div className="metric-tile">
              <span className="metric-label">RAM</span>
              <span className="metric-value">
                {host?.mem_used_pct != null ? `${host.mem_used_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Disk /</span>
              <span className="metric-value">
                {host?.disk_root_pct != null ? `${host.disk_root_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Load</span>
              <span className="metric-value">
                {host?.load_1m != null ? host.load_1m.toFixed(2) : '—'}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">GPU max</span>
              <span className="metric-value">
                {maxGpuUtil != null ? `${maxGpuUtil.toFixed(0)}%` : gpus.length === 0 ? '—' : 'n/a'}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">GPU temp</span>
              <span className="metric-value">
                {maxTemp != null ? `${maxTemp.toFixed(0)}°C` : '—'}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">GPUs</span>
              <span className="metric-value">{gpus.length || metrics?.gpu.length || '—'}</span>
            </div>
          </div>

          {testResult ? (
            <p className={`ssh-line ${testResult.success ? 'ok' : 'fail'}`}>
              SSH {testResult.success ? 'OK' : 'Failed'}
              {testResult.latency_ms != null ? ` · ${testResult.latency_ms} ms` : ''}
              {!testResult.success ? ` · ${testResult.message}` : ''}
            </p>
          ) : null}

          <div className="server-actions">
            <button type="button" className="btn ghost" disabled={testing} onClick={onTest}>
              {testing ? 'Testing…' : 'Test SSH'}
            </button>
            <button type="button" className="btn primary" disabled={collecting} onClick={onCollect}>
              {collecting ? 'Collecting…' : 'Collect metrics'}
            </button>
            <button type="button" className="btn ghost" disabled={investigating} onClick={onInvestigate}>
              {investigating ? 'Working…' : 'Investigate'}
            </button>
            <button type="button" className="btn ghost" onClick={onRequestRecollect}>
              Request recollect
            </button>
          </div>
        </>
      ) : (
        <p className="muted-block">
          {server.ssh_auth_mode === 'auto' && !server.has_ssh_password
            ? 'Waiting for SSH password (GPU hosts 165/166) or key access.'
            : 'SSH not configured yet — add key access or set password via API.'}
        </p>
      )}
    </article>
  )
}
