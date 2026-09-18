import { useCallback, useEffect, useState } from 'react'
import {
  fetchVoiceMgOverview,
  matchAiInsightExtra,
  type AiInsightExtra,
  type VoiceMgOverview,
  type VoiceMgSnapshot,
} from '../api'
import { AiInsightExtras } from './AiInsightExtras'
import { LegacyMetricsSection } from './LegacyMetricsSection'

function probeState(value: boolean | null): string {
  if (value == null) return 'Unknown'
  return value ? 'Running' : 'Check failed'
}

function services(snapshot: VoiceMgSnapshot): string {
  const workloadUp =
    snapshot.service_active === true ||
    (snapshot.app_process_count != null && snapshot.app_process_count > 0)
  const parts: string[] = []
  if (snapshot.service_active != null) {
    parts.push(`App ${probeState(snapshot.service_active)}`)
  }
  if (snapshot.app_process_count != null) {
    parts.push(`${snapshot.app_process_count} app procs`)
  }
  if (snapshot.containers_running != null && snapshot.containers_running > 0) {
    parts.push(`${snapshot.containers_running} containers`)
  }
  if (!workloadUp) {
    if (snapshot.docker_active != null) {
      parts.push(`Docker ${probeState(snapshot.docker_active)}`)
    }
    if (snapshot.nginx_active != null) {
      parts.push(`Nginx ${probeState(snapshot.nginx_active)}`)
    }
  }
  if (snapshot.extra_service_status) parts.push(snapshot.extra_service_status)
  return parts.join(' · ') || '—'
}

type Props = {
  extras?: AiInsightExtra[]
  isAdmin?: boolean
}

export function VoiceMgPanel({ extras = [], isAdmin = false }: Props) {
  const [overview, setOverview] = useState<VoiceMgOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setOverview(await fetchVoiceMgOverview())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load VoiceMG metrics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>VoiceMG</h1>
          <p>
            Read-only SSH for VMG and STT hosts: Docker, optional systemd units, process samples, and
            GPU summary on STT. “Check failed” means our probe failed, not necessarily that the host is
            offline.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </header>

      {error ? <p className="banner error">{error}</p> : null}

      {overview ? (
        <>
          <section className="panel">
            <div className="stat-row backupvault-stat-row">
              <div className="stat-card">
                <span className="stat-label">Hosts collected</span>
                <span className="stat-value">
                  {overview.collected_hosts}/{overview.total_hosts}
                </span>
              </div>
              <div className="stat-card">
                <span className="stat-label">VMG hosts</span>
                <span className="stat-value">{overview.vmg_hosts}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">STT hosts</span>
                <span className="stat-value">{overview.stt_hosts}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Service check failed</span>
                <span className="stat-value warn">{overview.service_down}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Storage ≥85%</span>
                <span className="stat-value warn">{overview.storage_warning}</span>
              </div>
            </div>
            <p className="muted backupvault-note">{overview.note}</p>
          </section>

          <section className="panel">
            <h2>Latest SSH snapshots</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Server</th>
                    <th>Role</th>
                    <th>Workload</th>
                    <th>GPU (STT)</th>
                    <th>Storage</th>
                    <th>Portal extras</th>
                    <th>Collected</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.servers.map((server) => {
                    const snapshot = server.snapshot
                    return (
                      <tr key={server.server_id}>
                        <td>
                          {server.server_name}
                          <br />
                          <span className="muted">{server.ip_address}</span>
                        </td>
                        <td>{snapshot?.role ?? (server.server_name.toLowerCase().includes('stt') ? 'stt' : 'vmg')}</td>
                        <td>
                          {snapshot ? (
                            <>
                              {services(snapshot)}
                              <br />
                              <span className="muted">
                                App signal: {probeState(snapshot.service_active)}
                              </span>
                            </>
                          ) : (
                            'Run fleet collect'
                          )}
                        </td>
                        <td>
                          {snapshot?.role === 'stt'
                            ? snapshot.gpu_device_count != null
                              ? `${snapshot.gpu_device_count} GPU(s)`
                              : 'No nvidia-smi'
                            : '—'}
                          {snapshot?.gpu_util_summary ? (
                            <span className="muted">
                              <br />
                              {snapshot.gpu_util_summary.split('\n')[0]}
                            </span>
                          ) : null}
                        </td>
                        <td>
                          {snapshot?.data_disk_used_pct != null
                            ? `${snapshot.data_mount ?? '/'} · ${snapshot.data_disk_used_pct.toFixed(1)}%`
                            : '—'}
                        </td>
                        <td>
                          {(() => {
                            const extra = matchAiInsightExtra(
                              extras,
                              server.ip_address,
                              server.server_name,
                            )
                            return extra ? <AiInsightExtras extra={extra} compact /> : '—'
                          })()}
                        </td>
                        <td>
                          {snapshot ? new Date(snapshot.collected_at).toLocaleString() : '—'}
                          {snapshot?.healthcheck_status ? (
                            <span className="muted">
                              <br />
                              {snapshot.healthcheck_status}
                            </span>
                          ) : null}
                          {snapshot?.collect_error &&
                          snapshot.service_active !== true ? (
                            <span className="backupvault-error" title={snapshot.collect_error}>
                              {' '}
                              · partial
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <LegacyMetricsSection
            domain="voicemg"
            title="Legacy VoiceMG portal (MariaDB sync)"
            isAdmin={isAdmin}
          />
        </>
      ) : null}
    </>
  )
}
