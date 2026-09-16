import { useCallback, useEffect, useState } from 'react'
import {
  fetchVoiceMgOverview,
  type VoiceMgOverview,
  type VoiceMgSnapshot,
} from '../api'

function probeState(value: boolean | null): string {
  if (value == null) return 'Unknown'
  return value ? 'Running' : 'Check failed'
}

function services(snapshot: VoiceMgSnapshot): string {
  const parts = [
    snapshot.docker_active == null ? null : `Docker ${probeState(snapshot.docker_active)}`,
    snapshot.nginx_active == null ? null : `Nginx ${probeState(snapshot.nginx_active)}`,
    snapshot.containers_running != null ? `${snapshot.containers_running} containers` : null,
    snapshot.app_process_count != null ? `${snapshot.app_process_count} app procs` : null,
    snapshot.extra_service_status,
  ].filter(Boolean)
  return parts.join(' · ') || '—'
}

export function VoiceMgPanel() {
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
                          {snapshot ? new Date(snapshot.collected_at).toLocaleString() : '—'}
                          {snapshot?.healthcheck_status ? (
                            <span className="muted">
                              <br />
                              {snapshot.healthcheck_status}
                            </span>
                          ) : null}
                          {snapshot?.collect_error ? (
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
        </>
      ) : null}
    </>
  )
}
