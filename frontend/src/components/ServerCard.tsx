import type { AiInsightExtra, VoiceMgExtra } from '../api'
import type { ConnectionTestResult, GpuMetric, MetricsBundle, Server } from '../types'
import { AiInsightExtras } from './AiInsightExtras'
import { VoiceMgExtras } from './VoiceMgExtras'

function uniqueGpusByIndex(rows: GpuMetric[]): GpuMetric[] {
  const byIndex = new Map<number, GpuMetric>()
  for (const g of rows) {
    if (!byIndex.has(g.gpu_index)) byIndex.set(g.gpu_index, g)
  }
  return [...byIndex.values()].sort((a, b) => a.gpu_index - b.gpu_index)
}
import { ApprovalRequestButtons } from './ApprovalRequestButtons'
import { HostServices } from './HostServices'
import { MetricBar } from './MetricBar'
import { ServerMetricsCharts } from './ServerMetricsCharts'

type Props = {
  server: Server
  metrics: MetricsBundle | null
  extra?: AiInsightExtra
  voicemgExtra?: VoiceMgExtra
  testResult: ConnectionTestResult | undefined
  testing: boolean
  collecting: boolean
  investigating: boolean
  onTest: () => void
  onCollect: () => void
  onInvestigate: () => void
  restartServices?: string[]
  onRequestRecollect: () => void
  onRequestSshVerify: () => void
  onRequestRestart?: (service: string) => void
  variant?: 'card' | 'host'
}

export function ServerCard({
  server,
  metrics,
  extra,
  voicemgExtra,
  testResult,
  testing,
  collecting,
  investigating,
  onTest,
  onCollect,
  onInvestigate,
  restartServices = [],
  onRequestRecollect,
  onRequestSshVerify,
  onRequestRestart,
  variant = 'card',
}: Props) {
  const host = metrics?.host[0]
  const isGpu = server.server_type === 'gpu'
  const gpus = uniqueGpusByIndex(
    (metrics?.gpu_latest?.length ? metrics.gpu_latest : metrics?.gpu.filter((g) => g.status === 'ok')) ??
      [],
  )
  const maxGpuUtil = gpus.length ? Math.max(...gpus.map((g) => g.utilization_pct ?? 0)) : null
  const maxTemp = gpus.length ? Math.max(...gpus.map((g) => g.temperature_c ?? 0)) : null
  const product = metrics?.gpu_product ?? null
  const insights = metrics?.gpu_insights ?? null

  const loadDisplay = host?.load_1m != null ? host.load_1m.toFixed(2) : '—'
  const loadPct = host?.load_1m != null ? Math.min(100, (host.load_1m / 8) * 100) : null
  const cpuUtil = insights?.cpu_util_pct ?? extra?.cpu_utilization ?? null
  const isHost = variant === 'host'
  const memPct = host?.mem_used_pct ?? extra?.memory_utilization ?? null
  const diskPct = host?.disk_root_pct ?? extra?.storage_utilization ?? null

  const gpuCards = gpus.map((g) => (
    <div key={g.gpu_index} className="gpu-per-card">
      <strong>GPU {g.gpu_index}</strong>
      <span>{g.utilization_pct != null ? `${g.utilization_pct.toFixed(0)}% util` : '—'}</span>
      <span>
        {g.mem_used_pct != null
          ? `${g.mem_used_pct.toFixed(0)}% VRAM`
          : g.mem_used_mb != null && g.mem_total_mb
            ? `${((g.mem_used_mb / g.mem_total_mb) * 100).toFixed(0)}% VRAM`
            : '—'}
      </span>
      <span>{g.temperature_c != null ? `${g.temperature_c.toFixed(0)}°C` : '—'}</span>
      <span className="gpu-per-meta">
        {g.power_w != null ? `${g.power_w.toFixed(0)} W` : '—'}
        {g.clock_mhz != null ? ` · ${g.clock_mhz.toFixed(0)} MHz` : ''}
      </span>
    </div>
  ))

  const actions = (
    <>
      <button type="button" className="btn ghost" disabled={testing} onClick={onTest}>
        {testing ? 'Testing…' : 'Test SSH'}
      </button>
      <button type="button" className="btn primary" disabled={collecting} onClick={onCollect}>
        {collecting ? 'Collecting…' : 'Collect metrics'}
      </button>
      <button type="button" className="btn ghost" disabled={investigating} onClick={onInvestigate}>
        {investigating ? 'Working…' : 'Investigate'}
      </button>
      <ApprovalRequestButtons
        restartServices={restartServices}
        onRecollect={onRequestRecollect}
        onSshVerify={onRequestSshVerify}
        onRestart={onRequestRestart}
      />
    </>
  )

  return (
    <article className="server-card">
      <div className="server-card-head">
        <div>
          <p className="server-card-label">
            {server.project ?? 'ai'} · {server.server_type ?? 'host'}
          </p>
          <h3 className="server-card-title">
            <span>{server.server_name}</span>
            <span className="server-card-ip">
              {server.ip_address}:{server.ssh_port}
            </span>
          </h3>
        </div>
        <div className="server-card-pills">
          {extra?.health_score != null ? (
            <span
              className={`bv-pill bv-pill--${
                extra.health_score >= 80 ? 'ok' : extra.health_score >= 60 ? 'partial' : 'fail'
              }`}
            >
              {extra.health_score}
            </span>
          ) : null}
          <span className={`status-pill ${server.is_active ? 'live' : 'off'}`}>
            {server.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
      </div>

      {server.is_active ? (
        <>
          {isHost ? (
            <>
              <div className="host-kpis">
                <div className="host-kpi">
                  <span>CPU load</span>
                  <strong>{loadDisplay}</strong>
                </div>
                <div className="host-kpi">
                  <span>Memory</span>
                  <strong>{memPct != null ? `${memPct.toFixed(0)}%` : '—'}</strong>
                </div>
                <div className="host-kpi">
                  <span>Disk</span>
                  <strong>{diskPct != null ? `${diskPct.toFixed(0)}%` : '—'}</strong>
                </div>
                <div className="host-kpi">
                  <span>Health</span>
                  <strong>{extra?.health_score != null ? extra.health_score : '—'}</strong>
                </div>
                <div className="host-kpi">
                  <span>Open alerts</span>
                  <strong>{extra?.open_alerts != null ? extra.open_alerts : '—'}</strong>
                </div>
              </div>
              <HostServices server={server} dockerActive={product?.docker_active} />
            </>
          ) : null}

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
              valuePct={memPct}
              display={memPct != null ? `${memPct.toFixed(1)}%` : '—'}
            />
            <MetricBar
              label="Disk /"
              valuePct={diskPct}
              display={diskPct != null ? `${diskPct.toFixed(1)}%` : '—'}
            />
            {cpuUtil != null ? (
              <MetricBar
                label="CPU util"
                valuePct={cpuUtil}
                display={`${cpuUtil.toFixed(1)}%`}
                warnAt={70}
                critAt={90}
              />
            ) : null}
          </div>

          {isGpu && (
            <>
              <div className="metric-grid gpu-metrics">
                <div className="metric-tile">
                  <span className="metric-label">GPU util avg</span>
                  <span className="metric-value">
                    {insights?.gpu_util_avg != null
                      ? `${insights.gpu_util_avg.toFixed(1)}%`
                      : maxGpuUtil != null
                        ? `${maxGpuUtil.toFixed(0)}%`
                        : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">GPU temp avg</span>
                  <span className="metric-value">
                    {insights?.gpu_temp_avg != null
                      ? `${insights.gpu_temp_avg.toFixed(1)}°C`
                      : maxTemp != null
                        ? `${maxTemp.toFixed(0)}°C`
                        : '—'}
                  </span>
                </div>
                <div className="metric-tile" title="Physical GPU indices on this host (nvidia-smi), not fleet host count">
                  <span className="metric-label">GPU devices</span>
                  <span className="metric-value">{gpus.length || '—'}</span>
                </div>
              </div>

              {gpus.length > 0 ? (
                isHost ? (
                  <div className="host-gpu">
                    <p className="metric-label">GPUs on this host</p>
                    <div className="gpu-per-cards">{gpuCards}</div>
                  </div>
                ) : (
                  <details className="gpu-detail-fold">
                    <summary>
                      Per-GPU ({gpus.length} device{gpus.length === 1 ? '' : 's'} on this host)
                    </summary>
                    <div className="gpu-per-cards">{gpuCards}</div>
                  </details>
                )
              ) : null}
            </>
          )}

          {isGpu && insights ? (
            <details className="gpu-detail-fold gpu-product-block">
              <summary>Host & network</summary>
              <div className="metric-grid gpu-metrics">
                <div className="metric-tile">
                  <span className="metric-label">App processes</span>
                  <span className="metric-value">
                    {insights.process_count != null ? insights.process_count : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">TCP conn</span>
                  <span className="metric-value">
                    {insights.tcp_connection_lines != null
                      ? insights.tcp_connection_lines
                      : insights.tcp_inuse != null
                        ? insights.tcp_inuse
                        : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">TCP established</span>
                  <span className="metric-value">
                    {insights.tcp_established != null ? insights.tcp_established : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">Listen :8000</span>
                  <span className="metric-value">
                    {insights.listen_port_8000 != null ? insights.listen_port_8000 : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">Listen :8011</span>
                  <span className="metric-value">
                    {insights.listen_port_8011 != null ? insights.listen_port_8011 : '—'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">Local ping</span>
                  <span className="metric-value">
                    {insights.localhost_ping_ok == null
                      ? '—'
                      : insights.localhost_ping_ok
                        ? 'ok'
                        : 'fail'}
                  </span>
                </div>
                <div className="metric-tile">
                  <span className="metric-label">Listen sockets</span>
                  <span className="metric-value">
                    {insights.listen_sockets != null ? insights.listen_sockets : '—'}
                  </span>
                </div>
              </div>
              {insights.collect_error ? (
                <p className="ssh-line fail">Insights collect: {insights.collect_error}</p>
              ) : null}
            </details>
          ) : null}

          {isGpu && product ? (
            <details className="gpu-detail-fold gpu-product-block">
              <summary>Product metrics (vLLM / Docker)</summary>
              <div className="metric-grid gpu-metrics">
                <div className="metric-tile">
                  <span className="metric-label">Compute jobs</span>
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
                <div className="metric-tile">
                  <span className="metric-label">Docker</span>
                  <span className="metric-value">
                    {product.docker_active == null ? '—' : product.docker_active ? 'active' : 'off'}
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
              {product.docker_container_status ? (
                <pre className="readonly-sample">{product.docker_container_status}</pre>
              ) : null}
              {product.process_sample ? (
                <pre className="readonly-sample">{product.process_sample}</pre>
              ) : null}
              {product.log_tail ? (
                <pre className="readonly-sample">{product.log_tail}</pre>
              ) : null}
              {product.collect_error ? (
                <p className="ssh-line fail">Product collect: {product.collect_error}</p>
              ) : null}
            </details>
          ) : null}

          {voicemgExtra ? <VoiceMgExtras extra={voicemgExtra} /> : null}
          {extra && !voicemgExtra ? <AiInsightExtras extra={extra} /> : null}

          {testResult ? (
            <p className={`ssh-line ${testResult.success ? 'ok' : 'fail'}`}>
              SSH {testResult.success ? 'OK' : 'Failed'}
              {testResult.latency_ms != null ? ` · ${testResult.latency_ms} ms` : ''}
              {!testResult.success ? ` · ${testResult.message}` : ''}
            </p>
          ) : null}

          {isHost ? (
            <>
              <ServerMetricsCharts
                serverId={server.id}
                serverName={server.server_name}
                isGpu={isGpu}
                defaultOpen
                chartHeight={140}
              />
              <div className="server-toolbar">
                <div className="server-actions">{actions}</div>
              </div>
            </>
          ) : (
            <div className="server-toolbar">
              <ServerMetricsCharts
                serverId={server.id}
                serverName={server.server_name}
                isGpu={isGpu}
              />
              <div className="server-actions">{actions}</div>
            </div>
          )}
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
