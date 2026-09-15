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
  const isGpu = server.server_type === 'gpu'
  const gpus = metrics?.gpu.filter((g) => g.status === 'ok') ?? []
  const maxGpuUtil = gpus.length ? Math.max(...gpus.map((g) => g.utilization_pct ?? 0)) : null
  const maxTemp = gpus.length ? Math.max(...gpus.map((g) => g.temperature_c ?? 0)) : null
  const product = metrics?.gpu_product ?? null

  const loadDisplay = host?.load_1m != null ? host.load_1m.toFixed(2) : '—'
  const loadPct = host?.load_1m != null ? Math.min(100, (host.load_1m / 8) * 100) : null

  return (
    <article className="server-card">
      <div className="server-card-head">
        <div>
          <p className="server-card-label">
            {server.project ?? 'ai'} · {server.server_type ?? 'host'}
          </p>
          <h3>{server.server_name}</h3>
          <p className="server-card-meta">
            {server.ip_address}:{server.ssh_port} · {server.ssh_username}
          </p>
        </div>
        <span className={`status-pill ${server.is_active ? 'live' : 'off'}`}>
          {server.is_active ? 'Active' : 'Inactive'}
        </span>
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
              display={host?.mem_used_pct != null ? `${host.mem_used_pct.toFixed(1)}%` : '—'}
            />
            <MetricBar
              label="Disk /"
              valuePct={host?.disk_root_pct ?? null}
              display={host?.disk_root_pct != null ? `${host.disk_root_pct.toFixed(1)}%` : '—'}
            />
          </div>

          {isGpu && (
            <div className="metric-grid gpu-metrics">
              <div className="metric-tile">
                <span className="metric-label">GPU max</span>
                <span className="metric-value">
                  {maxGpuUtil != null ? `${maxGpuUtil.toFixed(0)}%` : '—'}
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
                <span className="metric-value">{gpus.length || '—'}</span>
              </div>
            </div>
          )}

          {isGpu && product ? (
            <div className="gpu-product-block">
              <p className="server-card-label">Product metrics (SSH, read-only)</p>
              <div className="metric-grid gpu-metrics">
                <div className="metric-tile">
                  <span className="metric-label">GPU jobs</span>
                  <span className="metric-value">
                    {product.compute_process_count != null ? product.compute_process_count : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">Job VRAM</span>
                  <span className="metric-value">
                    {product.compute_mem_used_mb != null
                      ? `${product.compute_mem_used_mb.toFixed(0)} MiB`
                      : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">Docker up</span>
                  <span className="metric-value">
                    {product.docker_containers_running != null
                      ? product.docker_containers_running
                      : '—'}
                  </span>
                </div>
              </div>
              {product.gpu_model_name ? (
                <p className="muted product-meta">
                  {product.gpu_model_name}
                  {product.driver_version ? ` · driver ${product.driver_version}` : ''}
                </p>
              ) : null}
              {product.compute_process_names ? (
                <p className="muted product-meta">{product.compute_process_names}</p>
              ) : null}
              {product.collect_error ? (
                <p className="ssh-line fail">Product collect: {product.collect_error}</p>
              ) : null}
            </div>
          ) : null}

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
            ? 'Waiting for SSH password (GPU 165/166) or key access.'
            : 'SSH not configured yet — add key access or set password via API.'}
        </p>
      )}
    </article>
  )
}
