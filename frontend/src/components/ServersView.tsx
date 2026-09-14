import { useMemo, useState } from 'react'
import {
  FLEET_GROUPS,
  countInGroup,
  serverMatchesFleetGroup,
  type FleetGroupId,
} from '../lib/fleetGroups'
import { healthScoreFromHost } from '../lib/healthScore'
import type { Alert, ConnectionTestResult, MetricsBundle, Server } from '../types'
import { ServerCard } from './ServerCard'

type Props = {
  servers: Server[]
  metricsByServer: Record<number, MetricsBundle | null>
  testResults: Record<number, ConnectionTestResult>
  testingId: number | null
  collectingId: number | null
  investigatingId: number | null
  alerts: Alert[]
  onTest: (s: Server) => void
  onCollect: (s: Server) => void
  onInvestigate: (s: Server) => void
  onRequestRecollect: (s: Server) => void
  onRefresh: () => void
}

export function ServersView({
  servers,
  metricsByServer,
  testResults,
  testingId,
  collectingId,
  investigatingId,
  alerts,
  onTest,
  onCollect,
  onInvestigate,
  onRequestRecollect,
  onRefresh,
}: Props) {
  const [fleetGroup, setFleetGroup] = useState<FleetGroupId>('all')

  const activeServers = useMemo(() => servers.filter((s) => s.is_active), [servers])
  const pendingServers = useMemo(() => servers.filter((s) => !s.is_active), [servers])

  const filteredActive = useMemo(() => {
    if (fleetGroup === 'voicemg') return []
    return activeServers.filter((s) => serverMatchesFleetGroup(s, fleetGroup))
  }, [activeServers, fleetGroup])

  const openAlerts = alerts.filter((a) => a.status === 'open').length

  const avgHealth = useMemo(() => {
    const scores: number[] = []
    for (const s of filteredActive) {
      const h = healthScoreFromHost(metricsByServer[s.id]?.host[0])
      if (h != null) scores.push(h)
    }
    if (!scores.length) return null
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
  }, [filteredActive, metricsByServer])

  const groupDef = FLEET_GROUPS.find((g) => g.id === fleetGroup)

  return (
    <div className="obs-layout">
      <aside className="fleet-sidebar">
        <p className="fleet-sidebar-title">Server groups</p>
        <ul className="fleet-group-list">
          {FLEET_GROUPS.map((g) => {
            const n = countInGroup(servers, g.id, true)
            const total = countInGroup(servers, g.id, false)
            return (
              <li key={g.id}>
                <button
                  type="button"
                  className={`fleet-group-btn ${fleetGroup === g.id ? 'active' : ''}`}
                  onClick={() => setFleetGroup(g.id)}
                >
                  <span>{g.label}</span>
                  <span className="fleet-group-count">{n}/{total || n}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      <div className="obs-main">
        <header className="page-head">
          <div>
            <h1>Observability</h1>
            <p>{groupDef?.label ?? 'Fleet'} — host metrics for server operations</p>
          </div>
          <button type="button" className="btn ghost" onClick={onRefresh}>
            Refresh
          </button>
        </header>

        <div className="stat-row">
          <div className="stat-card">
            <span className="stat-label">Servers</span>
            <span className="stat-value">{filteredActive.length}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Online</span>
            <span className="stat-value accent">{filteredActive.length}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Avg health</span>
            <span className="stat-value">{avgHealth ?? '—'}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Open alerts</span>
            <span className="stat-value warn">{openAlerts}</span>
          </div>
        </div>

        {fleetGroup === 'voicemg' ? (
          <section className="placeholder-panel">
            <h2>Voice MG</h2>
            <p>{groupDef?.emptyHint}</p>
            <p className="muted">
              {countInGroup(servers, 'voicemg', false)} hosts are in inventory and will appear here
              after Voice MG metrics are integrated.
            </p>
          </section>
        ) : (
          <>
            <div className="server-grid compact">
              {filteredActive.map((s) => (
                <ServerCard
                  key={s.id}
                  server={s}
                  metrics={metricsByServer[s.id] ?? null}
                  testResult={testResults[s.id]}
                  testing={testingId === s.id}
                  collecting={collectingId === s.id}
                  investigating={investigatingId === s.id}
                  onTest={() => onTest(s)}
                  onCollect={() => onCollect(s)}
                  onInvestigate={() => onInvestigate(s)}
                  onRequestRecollect={() => onRequestRecollect(s)}
                />
              ))}
            </div>
            {filteredActive.length === 0 && (
              <p className="muted">No active servers in this group.</p>
            )}
          </>
        )}

        {pendingServers.length > 0 && (
          <section className="pending-section">
            <h2>Pending access ({pendingServers.length})</h2>
            <div className="pending-list">
              {pendingServers.map((s) => (
                <span key={s.id} className="pending-chip">
                  {s.server_name} · {s.ip_address}
                </span>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
