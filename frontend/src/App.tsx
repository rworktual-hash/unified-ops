import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  approveApproval,
  collectAllServerMetrics,
  collectServerMetrics,
  createApproval,
  fetchApprovalCatalog,
  fetchFleetCollectStatus,
  fetchHealth,
  type FleetCollectStatus,
  fetchMe,
  fetchAiInsightExtras,
  fetchVoiceMgExtras,
  fetchServerMetrics,
  matchAiInsightExtra,
  matchVoiceMgExtra,
  investigateAlert,
  investigateLiveAlert,
  investigateServer,
  listAgentActions,
  listAlerts,
  listLiveAlerts,
  listApprovals,
  listServers,
  rejectApproval,
  resolveAlert,
  testServerConnection,
  UnauthorizedError,
  type AiInsightExtra,
  type AppUser,
  type ApprovalCatalog,
  type VoiceMgExtra,
} from './api'
import { clearStoredToken } from './authStorage'
import { AiInsightsGroups } from './components/AiInsightsGroups'
import { useLivePoll } from './useLivePoll'
import { BackupVaultPanel } from './components/BackupVaultPanel'
import { ChatPanel } from './components/ChatPanel'
import { LoginPage } from './components/LoginPage'
import { ServerCard } from './components/ServerCard'
import { ServersByDomain } from './components/ServersByDomain'
import type { DomainId } from './serverDomains'
import { ApprovalRequestButtons } from './components/ApprovalRequestButtons'
import { EmailPanel } from './components/EmailPanel'
import { InfrastructurePanel } from './components/InfrastructurePanel'
import { LegacyMetricsSection } from './components/LegacyMetricsSection'
import { VoiceMgPanel } from './components/VoiceMgPanel'
import { UsersPanel } from './components/UsersPanel'
import type { AgentAction, Alert, Approval, ConnectionTestResult, LiveAlert, MetricsBundle, Server } from './types'
import './App.css'

type NavId =
  | 'servers'
  | 'infrastructure'
  | 'backupvault'
  | 'email'
  | 'voicemg'
  | 'chat'
  | 'alerts'
  | 'approvals'
  | 'activity'
  | 'users'

function App() {
  const [session, setSession] = useState<AppUser | null | 'pending'>('pending')
  const [nav, setNav] = useState<NavId>('servers')
  const [apiStatus, setApiStatus] = useState<'loading' | 'ok' | 'error'>('loading')
  const [servers, setServers] = useState<Server[]>([])
  const [error, setError] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResults, setTestResults] = useState<Record<number, ConnectionTestResult>>({})
  const [collectingId, setCollectingId] = useState<number | null>(null)
  const [metricsByServer, setMetricsByServer] = useState<Record<number, MetricsBundle | null>>({})
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [liveAlerts, setLiveAlerts] = useState<LiveAlert[]>([])
  const [liveAlertsReason, setLiveAlertsReason] = useState<string | null>(null)
  const [approvalCatalog, setApprovalCatalog] = useState<ApprovalCatalog>({
    safe_actions: ['recollect_metrics', 'ssh_verify'],
    restart_services: [],
  })
  const [showResolved, setShowResolved] = useState(false)
  const [agentActions, setAgentActions] = useState<AgentAction[]>([])
  const [investigatingId, setInvestigatingId] = useState<number | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [showAllApprovals, setShowAllApprovals] = useState(false)
  const [collectingAll, setCollectingAll] = useState(false)
  const [fleetStatus, setFleetStatus] = useState<FleetCollectStatus | null>(null)
  const [serverDomain, setServerDomain] = useState<DomainId>('ai')
  const [aiExtras, setAiExtras] = useState<AiInsightExtra[]>([])
  const [voiceMgExtras, setVoiceMgExtras] = useState<VoiceMgExtra[]>([])

  const activeServers = useMemo(() => servers.filter((s) => s.is_active), [servers])
  const pendingServers = useMemo(() => servers.filter((s) => !s.is_active), [servers])
  const monitoredServers = useMemo(() => activeServers, [activeServers])
  const emailServers = useMemo(
    () => activeServers.filter((s) => s.project === 'email'),
    [activeServers],
  )
  const backupVaultServers = useMemo(
    () => activeServers.filter((s) => s.project === 'backupvault'),
    [activeServers],
  )
  const infrastructureServers = useMemo(
    () =>
      activeServers.filter((s) => {
        const p = (s.project ?? '').toLowerCase()
        return p === 'infrastructure' || p === 'infra'
      }),
    [activeServers],
  )
  const voiceMgServers = useMemo(
    () => activeServers.filter((s) => (s.project ?? '').toLowerCase() === 'voicemg'),
    [activeServers],
  )

  const load = useCallback(async () => {
    setError(null)
    try {
      await fetchHealth()
      setApiStatus('ok')
    } catch (err) {
      setApiStatus('error')
      setError(err instanceof Error ? err.message : 'Cannot reach API. Start the backend on port 8000.')
      return
    }
    try {
      const list = await listServers()
      setServers(list)
      const metrics: Record<number, MetricsBundle | null> = {}
      await Promise.all(
        list
          .filter((s) => s.is_active)
          .map(async (s) => {
            try {
              metrics[s.id] = await fetchServerMetrics(s.id, 1)
            } catch {
              metrics[s.id] = null
            }
          }),
      )
      setMetricsByServer(metrics)
      try {
        const extras = await fetchAiInsightExtras()
        setAiExtras(extras.ok ? extras.servers : [])
      } catch {
        setAiExtras([])
      }
      try {
        const extras = await fetchVoiceMgExtras()
        setVoiceMgExtras(extras.ok ? extras.servers : [])
      } catch {
        setVoiceMgExtras([])
      }
      try {
        setFleetStatus(await fetchFleetCollectStatus())
      } catch {
        setFleetStatus(null)
      }
      setAlerts(await listAlerts(showResolved ? undefined : 'open'))
      try {
        const live = await listLiveAlerts()
        setLiveAlerts(live.ok ? live.alerts : [])
        setLiveAlertsReason(live.ok ? null : live.reason)
      } catch {
        setLiveAlerts([])
        setLiveAlertsReason('Failed to load live .222 alerts')
      }
      setAgentActions(await listAgentActions(15))
      setApprovals(await listApprovals(showAllApprovals ? undefined : 'pending'))
      try {
        setApprovalCatalog(await fetchApprovalCatalog())
      } catch {
        /* keep defaults */
      }
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        clearStoredToken()
        setSession(null)
        return
      }
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    }
  }, [showResolved, showAllApprovals])

  useEffect(() => {
    void fetchMe()
      .then((u) => {
        setSession(u)
      })
      .catch(() => {
        clearStoredToken()
        setSession(null)
      })
  }, [])

  useEffect(() => {
    if (session && session !== 'pending') void load()
  }, [session, load])

  const pollAiExtras = useCallback(async () => {
    try {
      const extras = await fetchAiInsightExtras()
      if (extras.ok) setAiExtras(extras.servers)
    } catch {
      /* keep last extras */
    }
  }, [])
  const pollVoiceMgExtras = useCallback(async () => {
    try {
      const extras = await fetchVoiceMgExtras()
      if (extras.ok) setVoiceMgExtras(extras.servers)
    } catch {
      /* keep last extras */
    }
  }, [])
  const loggedIn = Boolean(session && session !== 'pending')
  const pollLiveAlerts = useCallback(async () => {
    try {
      const live = await listLiveAlerts()
      if (live.ok) {
        setLiveAlerts(live.alerts)
        setLiveAlertsReason(null)
      }
    } catch {
      /* keep last live alerts */
    }
  }, [])
  useLivePoll(pollAiExtras, loggedIn && (nav === 'servers' || nav === 'infrastructure'))
  useLivePoll(pollVoiceMgExtras, loggedIn && nav === 'servers')
  useLivePoll(pollLiveAlerts, loggedIn && nav === 'alerts')

  const requestApproval = useCallback(
    async (
      serverId: number,
      actionKey: string,
      actionParams?: Record<string, string>,
      alertId?: number,
    ) => {
      setError(null)
      try {
        await createApproval({
          server_id: serverId,
          action_key: actionKey,
          action_params: actionParams,
          alert_id: alertId,
          request_notes: `${actionKey} after operator review`,
        })
        setApprovals(await listApprovals(showAllApprovals ? undefined : 'pending'))
        setNav('approvals')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Request failed')
      }
    },
    [showAllApprovals],
  )

  const navItems: { id: NavId; label: string }[] = [
    { id: 'servers', label: 'Servers' },
    ...(infrastructureServers.length > 0
      ? [{ id: 'infrastructure' as const, label: 'Infrastructure' }]
      : []),
    ...(backupVaultServers.length > 0
      ? [{ id: 'backupvault' as const, label: 'BackupVault' }]
      : []),
    ...(emailServers.length > 0 ? [{ id: 'email' as const, label: 'Email' }] : []),
    ...(voiceMgServers.length > 0 ? [{ id: 'voicemg' as const, label: 'VoiceMG' }] : []),
    { id: 'chat', label: 'Chat' },
    { id: 'alerts', label: 'Alerts' },
    { id: 'approvals', label: 'Approvals' },
    { id: 'activity', label: 'Agent log' },
    ...(session && session !== 'pending' && session.role === 'admin'
      ? [{ id: 'users' as const, label: 'Users' }]
      : []),
  ]

  if (session === 'pending') {
    return (
      <div className="login-shell">
        <p className="muted">Loading…</p>
      </div>
    )
  }

  if (!session) {
    return (
      <LoginPage
        onLoggedIn={() => {
          void fetchMe().then((u) => {
            setSession(u)
          })
        }}
      />
    )
  }

  const pageTitle = navItems.find((item) => item.id === nav)?.label ?? 'Dashboard'
  const initials = session.email.slice(0, 2).toUpperCase()

  return (
    <div className="app-shell app-shell--fixed">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">UO</div>
          <span className="brand-text">Unified Ops</span>
        </div>
        <p className="nav-kicker">Modules</p>
        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${nav === item.id ? 'active' : ''}`}
              onClick={() => setNav(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <p className="sidebar-meta">
            <span className={`api-dot ${apiStatus === 'ok' ? 'ok' : 'err'}`} />
            {apiStatus === 'ok' ? 'API connected' : apiStatus === 'loading' ? 'API…' : 'API offline'}
            <span className="sidebar-meta-sub">
              {activeServers.length} servers
            </span>
          </p>
          <button
            type="button"
            className="nav-item sidebar-signout"
            onClick={() => {
              clearStoredToken()
              setSession(null)
            }}
          >
            Logout
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-title">
            <span className="topbar-orb" aria-hidden />
            <h1>{pageTitle}</h1>
          </div>
          <div className="topbar-user" title={session.email}>
            <span>{initials}</span>
          </div>
        </header>
        <div className="main-body">
        {error && <p className="banner error">{error}</p>}

        {nav === 'servers' && (
          <>
            <header className="page-head">
              <div>
                <h1>Servers</h1>
                <p>
                  Host metrics (CPU load, memory, disk) for {monitoredServers.length} active hosts. Domain
                  tabs filter this grid; use sidebar{' '}
                  {infrastructureServers.length > 0 ? (
                    <>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => setNav('infrastructure')}
                      >
                        Infrastructure
                      </button>
                      ,{' '}
                    </>
                  ) : null}
                  BackupVault, Email, and VoiceMG for SSH role dashboards.
                </p>
                {fleetStatus ? (
                  <p className="muted fleet-collect-line">
                    Scheduled collect:{' '}
                    {fleetStatus.scheduled_collect_enabled
                      ? `every ${Math.round(fleetStatus.interval_seconds / 60)} min · read-only (no restart)`
                      : 'off — set METRICS_SCHEDULED_COLLECT_ENABLED=true on API host'}
                    {fleetStatus.last_run_at
                      ? ` · Last run ${new Date(fleetStatus.last_run_at).toLocaleString()} (${fleetStatus.last_servers_ok ?? 0} ok${
                          fleetStatus.last_servers_failed
                            ? `, ${fleetStatus.last_servers_failed} failed`
                            : ''
                        }, ${fleetStatus.last_trigger ?? '?'})`
                      : ' · No fleet run logged yet'}
                  </p>
                ) : null}
              </div>
              {session.role === 'admin' && (
                <button
                  type="button"
                  className="btn primary"
                  disabled={collectingAll}
                  onClick={async () => {
                    setCollectingAll(true)
                    setError(null)
                    try {
                      const result = await collectAllServerMetrics(true)
                      if (result.mode === 'celery_queued') {
                        setError('Collect all queued in Celery — refresh in a few minutes.')
                      } else {
                        try {
                          setFleetStatus(await fetchFleetCollectStatus())
                        } catch {
                          /* keep previous line */
                        }
                        await load()
                        if (result.servers_failed > 0) {
                          setError(
                            `Collected ${result.servers_collected} servers; ${result.servers_failed} failed (SSH/timeout).`,
                          )
                        }
                      }
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Collect all failed')
                    } finally {
                      setCollectingAll(false)
                    }
                  }}
                >
                  {collectingAll ? 'Collecting all…' : 'Collect all servers'}
                </button>
              )}
            </header>

            <AiInsightsGroups extras={aiExtras} />

            <ServersByDomain
              servers={monitoredServers}
              domainFilter={serverDomain}
              onDomainFilterChange={setServerDomain}
              renderCard={(s) => (
                <ServerCard
                  key={s.id}
                  server={s}
                  metrics={metricsByServer[s.id] ?? null}
                  extra={
                    s.project === 'voicemg'
                      ? undefined
                      : matchAiInsightExtra(aiExtras, s.ip_address, s.server_name)
                  }
                  voicemgExtra={
                    s.project === 'voicemg'
                      ? matchVoiceMgExtra(voiceMgExtras, s.ip_address, s.server_name)
                      : undefined
                  }
                  testResult={testResults[s.id]}
                  testing={testingId === s.id}
                  collecting={collectingId === s.id}
                  investigating={investigatingId === s.id}
                  onTest={async () => {
                    setTestingId(s.id)
                    setError(null)
                    try {
                      const result = await testServerConnection(s.id)
                      setTestResults((prev) => ({ ...prev, [s.id]: result }))
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Connection test failed')
                    } finally {
                      setTestingId(null)
                    }
                  }}
                  onCollect={async () => {
                    setCollectingId(s.id)
                    setError(null)
                    try {
                      const bundle = await collectServerMetrics(s.id)
                      setMetricsByServer((prev) => ({ ...prev, [s.id]: bundle }))
                      setAlerts(await listAlerts(showResolved ? undefined : 'open'))
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Collect failed')
                    } finally {
                      setCollectingId(null)
                    }
                  }}
                  onInvestigate={async () => {
                    setInvestigatingId(s.id)
                    setError(null)
                    try {
                      await investigateServer(s.id)
                      setAgentActions(await listAgentActions(15))
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Investigate failed')
                    } finally {
                      setInvestigatingId(null)
                    }
                  }}
                  restartServices={approvalCatalog.restart_services}
                  onRequestRecollect={() => void requestApproval(s.id, 'recollect_metrics')}
                  onRequestSshVerify={() => void requestApproval(s.id, 'ssh_verify')}
                  onRequestRestart={(service) =>
                    void requestApproval(s.id, 'systemctl_restart', { service_name: service })
                  }
                />
              )}
            />

            {serverDomain === 'ai' && (
              <LegacyMetricsSection
                domain="ai_insights"
                title="Legacy AI Insights portal (MariaDB sync)"
                isAdmin={session?.role === 'admin'}
              />
            )}

            {pendingServers.length > 0 && (
              <section className="pending-section">
                <h2>Pending SSH access</h2>
                <div className="pending-list">
                  {pendingServers.map((s) => (
                    <span key={s.id} className="pending-chip">
                      {s.server_name} · {s.ip_address}
                    </span>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {nav === 'email' && session && emailServers.length > 0 && (
          <EmailPanel emailServers={emailServers} session={session} />
        )}

        {nav === 'infrastructure' && infrastructureServers.length > 0 && (
          <InfrastructurePanel extras={aiExtras} isAdmin={session?.role === 'admin'} />
        )}

        {nav === 'backupvault' && backupVaultServers.length > 0 && (
          <BackupVaultPanel isAdmin={session?.role === 'admin'} />
        )}

        {nav === 'voicemg' && voiceMgServers.length > 0 && (
          <VoiceMgPanel isAdmin={session?.role === 'admin'} />
        )}

        {nav === 'chat' && (
          <div className="chat-page">
            <header className="page-head page-head-compact">
              <h1>Chat</h1>
              <p className="muted">Uses server inventory, metrics, and alerts from this dashboard.</p>
            </header>
            <ChatPanel activeServers={activeServers} />
          </div>
        )}

        {nav === 'alerts' && (
          <>
            <header className="page-head">
              <h1>Alerts</h1>
              <p>
                SSH Collect alerts plus live <code>.222</code> AI Insights alerts. Investigate is
                read-only. Recollect and SSH verify wait on Approvals — nothing runs until you
                Approve.
              </p>
            </header>
            <section className="panel">
              <div className="panel-head">
                <h2>Live .222 ({liveAlerts.length})</h2>
              </div>
              {liveAlertsReason ? <p className="muted">{liveAlertsReason}</p> : null}
              {liveAlerts.length === 0 && !liveAlertsReason ? (
                <p className="muted">No open AI Insights alerts on .222, or none matched yet.</p>
              ) : liveAlerts.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Host</th>
                        <th>Title</th>
                        <th>Message</th>
                        <th>Match</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {liveAlerts.map((a) => (
                        <tr key={`live-${a.source_id}`}>
                          <td>
                            <span className={`badge ${a.severity}`}>{a.severity}</span>
                          </td>
                          <td>
                            {a.inventory_server_name || a.portal_server_name || '—'}
                            <br />
                            <span className="muted">{a.ip_address || a.hostname || '—'}</span>
                          </td>
                          <td>{a.title}</td>
                          <td>{a.message}</td>
                          <td>
                            {!a.matched
                              ? 'unmatched'
                              : a.inventory_active
                                ? 'inventory'
                                : 'inactive'}
                          </td>
                          <td className="action-cell">
                            <button
                              type="button"
                              className="btn ghost"
                              title={
                                a.matched && !a.inventory_active
                                  ? 'Host is paused (165/166) until SSH works'
                                  : undefined
                              }
                              disabled={!a.matched || !a.inventory_active || investigatingId === a.source_id}
                              onClick={async () => {
                                setInvestigatingId(a.source_id)
                                setError(null)
                                try {
                                  await investigateLiveAlert(a.source_id)
                                  setAgentActions(await listAgentActions(15))
                                } catch (err) {
                                  setError(err instanceof Error ? err.message : 'Investigate failed')
                                } finally {
                                  setInvestigatingId(null)
                                }
                              }}
                            >
                              Investigate
                            </button>
                            {a.inventory_server_id && a.inventory_active ? (
                              <ApprovalRequestButtons
                                restartServices={approvalCatalog.restart_services}
                                onRecollect={() =>
                                  void requestApproval(a.inventory_server_id!, 'recollect_metrics')
                                }
                                onSshVerify={() => void requestApproval(a.inventory_server_id!, 'ssh_verify')}
                                onRestart={(service) =>
                                  void requestApproval(a.inventory_server_id!, 'systemctl_restart', {
                                    service_name: service,
                                  })
                                }
                              />
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>SSH Collect ({alerts.filter((a) => a.status === 'open').length})</h2>
                <label className="checkbox inline">
                  <input
                    type="checkbox"
                    checked={showResolved}
                    onChange={(e) => setShowResolved(e.target.checked)}
                  />
                  Show resolved
                </label>
              </div>
              {alerts.length === 0 ? (
                <p className="muted">No alerts. Collect metrics on 148 or 149 to evaluate rules.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Server</th>
                        <th>Title</th>
                        <th>Message</th>
                        <th>Status</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {alerts.map((a) => (
                        <tr key={a.id}>
                          <td>
                            <span className={`badge ${a.severity}`}>{a.severity}</span>
                          </td>
                          <td>{a.server_name}</td>
                          <td>{a.title}</td>
                          <td>{a.message}</td>
                          <td>{a.status}</td>
                          <td className="action-cell">
                            {a.status === 'open' && (
                              <>
                                <button
                                  type="button"
                                  className="btn ghost"
                                  disabled={investigatingId === a.id}
                                  onClick={async () => {
                                    setInvestigatingId(a.id)
                                    try {
                                      await investigateAlert(a.id)
                                      setAgentActions(await listAgentActions(15))
                                    } finally {
                                      setInvestigatingId(null)
                                    }
                                  }}
                                >
                                  Investigate
                                </button>
                                <button
                                  type="button"
                                  className="btn ghost"
                                  onClick={async () => {
                                    await resolveAlert(a.id)
                                    setAlerts(await listAlerts(showResolved ? undefined : 'open'))
                                  }}
                                >
                                  Resolve
                                </button>
                                <ApprovalRequestButtons
                                  restartServices={approvalCatalog.restart_services}
                                  onRecollect={() =>
                                    void requestApproval(a.server_id, 'recollect_metrics', undefined, a.id)
                                  }
                                  onSshVerify={() =>
                                    void requestApproval(a.server_id, 'ssh_verify', undefined, a.id)
                                  }
                                  onRestart={(service) =>
                                    void requestApproval(
                                      a.server_id,
                                      'systemctl_restart',
                                      { service_name: service },
                                      a.id,
                                    )
                                  }
                                />
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}

        {nav === 'approvals' && (
          <>
            <header className="page-head">
              <h1>Approvals</h1>
              <p>
                Recollect and SSH verify wait here. Restart only if a service is allowlisted — never
                automatic.
              </p>
            </header>
            <section className="panel">
              <div className="panel-head">
                <h2>Queue ({approvals.filter((a) => a.status === 'pending').length} pending)</h2>
                <label className="checkbox inline">
                  <input
                    type="checkbox"
                    checked={showAllApprovals}
                    onChange={(e) => setShowAllApprovals(e.target.checked)}
                  />
                  Show all history
                </label>
              </div>
              {approvals.length === 0 ? (
                <p className="muted">
                  No approvals. Request recollect or SSH verify from a server card or an alert.
                </p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Server</th>
                        <th>Action</th>
                        <th>Status</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {approvals.map((ap) => (
                        <tr key={ap.id}>
                          <td>{ap.server_name}</td>
                          <td>
                            {ap.action_key}
                            {ap.action_params ? (
                              <>
                                <br />
                                <span className="muted">{ap.action_params}</span>
                              </>
                            ) : null}
                          </td>
                          <td>{ap.status}</td>
                          <td className="action-cell">
                            {ap.status === 'pending' && (
                              <>
                                <button
                                  type="button"
                                  className="btn primary"
                                  onClick={async () => {
                                    await approveApproval(ap.id)
                                    await load()
                                  }}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="btn ghost"
                                  onClick={async () => {
                                    await rejectApproval(ap.id)
                                    setApprovals(
                                      await listApprovals(showAllApprovals ? undefined : 'pending'),
                                    )
                                  }}
                                >
                                  Reject
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}

        {nav === 'users' && session.role === 'admin' && <UsersPanel />}

        {nav === 'activity' && (
          <>
            <header className="page-head">
              <h1>Agent log</h1>
              <p>Investigations and approved executions.</p>
            </header>
            <section className="panel">
              {agentActions.length === 0 ? (
                <p className="muted">No activity yet. Run Investigate on a connected server.</p>
              ) : (
                <ul className="agent-log">
                  {agentActions.map((aa) => (
                    <li key={aa.id}>
                      <strong>{aa.summary}</strong>
                      <span className="muted">
                        {' '}
                        · server #{aa.server_id} · {aa.action_type} · {aa.recommendation}
                      </span>
                      <pre className="diagnosis">{aa.diagnosis}</pre>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}

        {nav !== 'chat' && (
          <p className="muted" style={{ marginTop: '1.5rem' }}>
            <button type="button" className="btn ghost" onClick={() => void load()}>
              Refresh all
            </button>
          </p>
        )}
        </div>
      </main>
    </div>
  )
}

export default App
