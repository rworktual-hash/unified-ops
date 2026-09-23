import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  approveApproval,
  collectAllServerMetrics,
  collectServerMetrics,
  createApproval,
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
  listLiveSuggestions,
  fetchLiveAlertInDepth,
  listApprovals,
  listServers,
  rejectApproval,
  resolveAlert,
  testServerConnection,
  UnauthorizedError,
  type AiInsightExtra,
  type AppUser,
  type VoiceMgExtra,
} from './api'
import { clearStoredToken } from './authStorage'
import { formatWhen } from './formatWhen'
import { AiInsightsGroups } from './components/AiInsightsGroups'
import { useLivePoll } from './useLivePoll'
import { BackupVaultPanel } from './components/BackupVaultPanel'
import { ChatPanel } from './components/ChatPanel'
import { LoginPage } from './components/LoginPage'
import { ServerCard } from './components/ServerCard'
import { ServerDetail } from './components/ServerDetail'
import { ServersByDomain } from './components/ServersByDomain'
import type { DomainId } from './serverDomains'
import { ApprovalDecisionCard } from './components/ApprovalDecisionCard'
import { ApprovalRequestButtons } from './components/ApprovalRequestButtons'
import { BrandLockup } from './components/BrandLockup'
import { NavIcon } from './components/NavIcon'
import { AccountMenu } from './components/AccountMenu'
import { AgentLogList } from './components/AgentLogList'
import { EmailPanel } from './components/EmailPanel'
import { InfrastructurePanel } from './components/InfrastructurePanel'
import { VoiceMgPanel } from './components/VoiceMgPanel'
import { UsersPanel } from './components/UsersPanel'
import type {
  AgentAction,
  Alert,
  AlertSuggestion,
  Approval,
  ConnectionTestResult,
  LiveAlert,
  MetricsBundle,
  Server,
} from './types'
import './App.css'

function fleetStatusLine(hostCount: number, status: FleetCollectStatus | null) {
  const hosts = `${hostCount} host${hostCount === 1 ? '' : 's'}`
  if (!status?.last_run_at) return `${hosts} · No collect yet`
  const when = new Date(status.last_run_at).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const ok = status.last_servers_ok ?? 0
  const failed = status.last_servers_failed ?? 0
  return `${hosts} · Last collect ${when} · ${ok} ok · ${failed} failed`
}

type NavId =
  | 'servers'
  | 'hosts'
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
  const [nav, setNav] = useState<NavId>('alerts')
  const [servers, setServers] = useState<Server[]>([])
  const [error, setError] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResults, setTestResults] = useState<Record<number, ConnectionTestResult>>({})
  const [collectingId, setCollectingId] = useState<number | null>(null)
  const [metricsByServer, setMetricsByServer] = useState<Record<number, MetricsBundle | null>>({})
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [liveAlerts, setLiveAlerts] = useState<LiveAlert[]>([])
  const [liveAlertsReason, setLiveAlertsReason] = useState<string | null>(null)
  const [showResolved, setShowResolved] = useState(false)
  const [agentActions, setAgentActions] = useState<AgentAction[]>([])
  const [investigatingId, setInvestigatingId] = useState<number | null>(null)
  const [suggestions, setSuggestions] = useState<Record<number, AlertSuggestion>>({})
  const [inDepth, setInDepth] = useState<Record<number, string>>({})
  const [inDepthOpen, setInDepthOpen] = useState<Record<number, boolean>>({})
  const [inDepthId, setInDepthId] = useState<number | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [showAllApprovals, setShowAllApprovals] = useState(false)
  const [collectingAll, setCollectingAll] = useState(false)
  const [fleetStatus, setFleetStatus] = useState<FleetCollectStatus | null>(null)
  const [serverDomain, setServerDomain] = useState<DomainId>('ai')
  const [detailServerId, setDetailServerId] = useState<number | null>(null)
  const mainBodyRef = useRef<HTMLDivElement>(null)
  const listScrollRef = useRef(0)
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
    } catch (err) {
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
  const liveSuggestionKey = liveAlerts.map((alert) => alert.source_id).join(',')
  useEffect(() => {
    if (!loggedIn || nav !== 'alerts' || !liveSuggestionKey) return
    let stop = false
    let timer = 0
    const tick = async () => {
      try {
        const res = await listLiveSuggestions()
        if (stop) return
        setSuggestions((prev) => {
          const next = { ...prev }
          for (const row of res.suggestions) next[row.source_id] = row
          return next
        })
        if (res.pending_ids.length > 0) {
          timer = window.setTimeout(() => void tick(), 3000)
        }
      } catch {
        if (!stop) timer = window.setTimeout(() => void tick(), 8000)
      }
    }
    void tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [loggedIn, nav, liveSuggestionKey])

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

  const recoveryServices = useCallback(
    (serverId: number | null | undefined) => {
      const host = servers.find((s) => s.id === serverId)
      if (!host?.is_active || host.ip_address === '10.180.1.222') return []
      const project = (host.project || '').toLowerCase()
      const kind = (host.server_type || '').toLowerCase()
      if (kind === 'gpu' || project === 'voicemg' || project === 'backupvault' || kind === 'sip' || kind === 'pbx') {
        return ['docker']
      }
      if (project === 'email') return ['postfix']
      if (kind === 'nginx') return ['nginx']
      if (kind === 'kong') return ['kong']
      if (kind === 'monitoring') return ['grafana-server']
      return []
    },
    [servers],
  )

  const navItems: { id: NavId; label: string }[] = [
    { id: 'servers', label: 'Servers' },
    { id: 'hosts', label: 'Hosts' },
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

  const detailServer = monitoredServers.find((s) => s.id === detailServerId) ?? null

  function insightFor(server: Server) {
    return server.project === 'voicemg'
      ? undefined
      : matchAiInsightExtra(aiExtras, server.ip_address, server.server_name)
  }

  function openInsightHost(row: { ip_address: string; server_name: string; hostname: string | null }) {
    const host =
      monitoredServers.find((s) => row.ip_address && s.ip_address === row.ip_address) ||
      monitoredServers.find(
        (s) =>
          s.server_name.toLowerCase() === row.server_name.toLowerCase() ||
          s.server_name.toLowerCase() === (row.hostname || '').toLowerCase(),
      )
    if (!host) return false
    openHost(host.id)
    return true
  }

  function openHost(id: number) {
    listScrollRef.current = mainBodyRef.current?.scrollTop ?? 0
    setDetailServerId(id)
    requestAnimationFrame(() => mainBodyRef.current?.scrollTo({ top: 0 }))
  }

  function closeHost() {
    const top = listScrollRef.current
    setDetailServerId(null)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => mainBodyRef.current?.scrollTo({ top }))
    })
  }

  const pageTitle = nav === 'users' ? 'Users' : (navItems.find((item) => item.id === nav)?.label ?? 'Servers')

  return (
    <div className="app-shell app-shell--fixed">
      <aside className="sidebar">
        <BrandLockup />
        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${nav === item.id ? 'active' : ''}`}
              onClick={() => {
                setDetailServerId(null)
                setNav(item.id)
              }}
            >
              <NavIcon id={item.id} />
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-title">
            <h1>{pageTitle}</h1>
          </div>
          <AccountMenu
            user={session}
            onLogout={() => {
              clearStoredToken()
              setSession(null)
            }}
            onOpenUsers={
              session.role === 'admin'
                ? () => {
                    setNav('users')
                  }
                : undefined
            }
          />
        </header>
        <div className="main-body" ref={mainBodyRef}>
        {error && <p className="banner error">{error}</p>}

        {nav === 'servers' && !detailServer && (
          <>
            <header className="page-head servers-status">
              <p className="fleet-status-line">{fleetStatusLine(monitoredServers.length, fleetStatus)}</p>
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
            <AiInsightsGroups extras={aiExtras} onOpenHost={openInsightHost} />
          </>
        )}

        {nav === 'hosts' && !detailServer && (
          <>
            <header className="page-head">
              <p className="fleet-status-line">{monitoredServers.length} hosts</p>
            </header>
            <ServersByDomain
              servers={monitoredServers}
              domainFilter={serverDomain}
              onDomainFilterChange={setServerDomain}
              renderCard={(s) => {
                const host = metricsByServer[s.id]?.host[0]
                return (
                  <button
                    key={s.id}
                    type="button"
                    className="server-tile"
                    onClick={() => openHost(s.id)}
                  >
                    <strong>{s.server_name}</strong>
                    <span className="server-tile-ip">
                      {s.ip_address}:{s.ssh_port}
                    </span>
                    <span className="server-tile-metrics">
                      RAM {host?.mem_used_pct != null ? `${host.mem_used_pct.toFixed(0)}%` : '—'} · Disk{' '}
                      {host?.disk_root_pct != null ? `${host.disk_root_pct.toFixed(0)}%` : '—'}
                    </span>
                  </button>
                )
              }}
            />
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

        {detailServer && (nav === 'servers' || nav === 'hosts') && (
              <ServerDetail
                server={detailServer}
                extra={insightFor(detailServer)}
                onBack={closeHost}
              >
                <ServerCard
                  server={detailServer}
                  metrics={metricsByServer[detailServer.id] ?? null}
                  extra={insightFor(detailServer)}
                  voicemgExtra={
                    detailServer.project === 'voicemg'
                      ? matchVoiceMgExtra(voiceMgExtras, detailServer.ip_address, detailServer.server_name)
                      : undefined
                  }
                  testResult={testResults[detailServer.id]}
                  testing={testingId === detailServer.id}
                  collecting={collectingId === detailServer.id}
                  investigating={investigatingId === detailServer.id}
                  onTest={async () => {
                    setTestingId(detailServer.id)
                    setError(null)
                    try {
                      const result = await testServerConnection(detailServer.id)
                      setTestResults((prev) => ({ ...prev, [detailServer.id]: result }))
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Connection test failed')
                    } finally {
                      setTestingId(null)
                    }
                  }}
                  onCollect={async () => {
                    setCollectingId(detailServer.id)
                    setError(null)
                    try {
                      const bundle = await collectServerMetrics(detailServer.id)
                      setMetricsByServer((prev) => ({ ...prev, [detailServer.id]: bundle }))
                      setAlerts(await listAlerts(showResolved ? undefined : 'open'))
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Collect failed')
                    } finally {
                      setCollectingId(null)
                    }
                  }}
                  onInvestigate={async () => {
                    setInvestigatingId(detailServer.id)
                    setError(null)
                    try {
                      await investigateServer(detailServer.id)
                      setAgentActions(await listAgentActions(15))
                      setApprovals(await listApprovals(showAllApprovals ? undefined : 'pending'))
                      setNav('approvals')
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Investigate failed')
                    } finally {
                      setInvestigatingId(null)
                    }
                  }}
                  restartServices={recoveryServices(detailServer.id)}
                  variant={nav === 'hosts' ? 'host' : 'card'}
                  onRequestRecollect={() => void requestApproval(detailServer.id, 'recollect_metrics')}
                  onRequestSshVerify={() => void requestApproval(detailServer.id, 'ssh_verify')}
                  onRequestRestart={(service) =>
                    void requestApproval(detailServer.id, 'systemctl_restart', { service_name: service })
                  }
                />
              </ServerDetail>
        )}

        {nav === 'email' && session && emailServers.length > 0 && (
          <EmailPanel emailServers={emailServers} session={session} />
        )}

        {nav === 'infrastructure' && infrastructureServers.length > 0 && (
          <InfrastructurePanel extras={aiExtras} />
        )}

        {nav === 'backupvault' && backupVaultServers.length > 0 && (
          <BackupVaultPanel isAdmin={session?.role === 'admin'} />
        )}

        {nav === 'voicemg' && voiceMgServers.length > 0 && (
          <VoiceMgPanel />
        )}

        {nav === 'chat' && (
          <div className="chat-page">
            <ChatPanel activeServers={activeServers} />
          </div>
        )}

        {nav === 'alerts' && (
          <>
            <header className="page-head servers-status">
              <p className="fleet-status-line">
                {liveAlerts.length} live · {alerts.filter((a) => a.status === 'open').length} SSH
              </p>
              <label className="checkbox inline">
                <input
                  type="checkbox"
                  checked={showResolved}
                  onChange={(e) => setShowResolved(e.target.checked)}
                />
                Show resolved
              </label>
            </header>
            <section className="panel">
              <div className="panel-head">
                <h2>Live</h2>
              </div>
              {liveAlertsReason ? <p className="muted">{liveAlertsReason}</p> : null}
              {liveAlerts.length === 0 && !liveAlertsReason ? (
                <p className="muted">No open live alerts.</p>
              ) : liveAlerts.length > 0 ? (
                <div className="alert-list">
                  {liveAlerts.map((a) => (
                    <article className="alert-item" key={`live-${a.source_id}`}>
                      <span className={`badge ${a.severity}`}>{a.severity}</span>
                      <div className="alert-copy">
                        <div className="alert-title-line">
                          <strong>{a.inventory_server_name || a.portal_server_name || '—'}</strong>
                          <span className="muted">{a.ip_address || a.hostname || '—'}</span>
                          <span
                            className={`badge ${
                              !a.matched ? 'rejected' : a.inventory_active ? 'executed' : 'pending'
                            }`}
                          >
                            {!a.matched ? 'Unmatched' : a.inventory_active ? 'Inventory' : 'Paused'}
                          </span>
                        </div>
                        <p className="alert-title">{a.title}</p>
                        <p className="alert-message" title={a.message}>
                          {a.message}
                        </p>
                      </div>
                      <time className="alert-when">{formatWhen(a.last_seen_at || a.first_seen_at)}</time>
                      <div className="alert-actions">
                        <button
                          type="button"
                          className="btn ghost"
                          disabled={inDepthId === a.source_id}
                          onClick={async () => {
                            if (inDepthOpen[a.source_id]) {
                              setInDepthOpen((prev) => ({ ...prev, [a.source_id]: false }))
                              return
                            }
                            if (inDepth[a.source_id]) {
                              setInDepthOpen((prev) => ({ ...prev, [a.source_id]: true }))
                              return
                            }
                            setInDepthId(a.source_id)
                            setError(null)
                            try {
                              const row = await fetchLiveAlertInDepth(a.source_id)
                              setInDepth((prev) => ({ ...prev, [a.source_id]: row.detail }))
                              setInDepthOpen((prev) => ({ ...prev, [a.source_id]: true }))
                            } catch (err) {
                              setError(err instanceof Error ? err.message : 'In-depth suggestion failed')
                            } finally {
                              setInDepthId(null)
                            }
                          }}
                        >
                          {inDepthId === a.source_id
                            ? 'Preparing…'
                            : inDepthOpen[a.source_id]
                              ? 'Hide in-depth'
                              : 'In-depth suggestion'}
                        </button>
                        {!a.matched || !a.inventory_active ? (
                          <span className="muted">No agent</span>
                        ) : (
                          <button
                            type="button"
                            className="btn ghost"
                            disabled={investigatingId === a.source_id}
                            onClick={async () => {
                              setInvestigatingId(a.source_id)
                              setError(null)
                              try {
                                await investigateLiveAlert(a.source_id)
                                setAgentActions(await listAgentActions(15))
                                setApprovals(await listApprovals(showAllApprovals ? undefined : 'pending'))
                                setNav('approvals')
                              } catch (err) {
                                setError(err instanceof Error ? err.message : 'Investigate failed')
                              } finally {
                                setInvestigatingId(null)
                              }
                            }}
                          >
                            Investigate
                          </button>
                        )}
                        {a.inventory_server_id && a.inventory_active ? (
                          <ApprovalRequestButtons
                            restartServices={recoveryServices(a.inventory_server_id)}
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
                      </div>
                      {suggestions[a.source_id] ? (
                        <div className="alert-suggest">
                          <p>
                            <span>Why</span>
                            {suggestions[a.source_id].why}
                          </p>
                          <p>
                            <span>Fix</span>
                            {suggestions[a.source_id].solution}
                          </p>
                          <p>
                            <span>Team</span>
                            {suggestions[a.source_id].team}
                          </p>
                          <p>
                            <span>Time</span>
                            {suggestions[a.source_id].time_estimate}
                          </p>
                          <p className="muted alert-suggest-note">
                            {suggestions[a.source_id].from_model
                              ? 'Estimate only. A restart still needs Approve and Confirm run.'
                              : 'The model was unavailable, so this is a short read of the alert. A restart still needs Approve and Confirm run.'}
                          </p>
                          {inDepthOpen[a.source_id] && inDepth[a.source_id] ? (
                            <div className="alert-depth">
                              <span>In depth</span>
                              {inDepth[a.source_id]}
                            </div>
                          ) : null}
                        </div>
                      ) : (
                        <p className="muted alert-suggest-note">Preparing suggestion…</p>
                      )}
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>SSH Collect</h2>
              </div>
              {alerts.length === 0 ? (
                <p className="muted">No SSH alerts.</p>
              ) : (
                <div className="alert-list">
                  {alerts.map((a) => (
                    <article className="alert-item" key={a.id}>
                      <span className={`badge ${a.severity}`}>{a.severity}</span>
                      <div className="alert-copy">
                        <div className="alert-title-line">
                          <strong>{a.server_name}</strong>
                          <span className="muted">{a.ip_address}</span>
                          <span className={`badge ${a.status === 'open' ? 'pending' : 'executed'}`}>
                            {a.status}
                          </span>
                        </div>
                        <p className="alert-title">{a.title}</p>
                        <p className="alert-message" title={a.message}>
                          {a.message}
                        </p>
                      </div>
                      <time className="alert-when">{formatWhen(a.last_seen_at)}</time>
                      <div className="alert-actions">
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
                                  setApprovals(
                                    await listApprovals(showAllApprovals ? undefined : 'pending'),
                                  )
                                  setNav('approvals')
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
                              restartServices={recoveryServices(a.server_id)}
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
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        {nav === 'approvals' && (
          <>
            <header className="page-head servers-status">
              <p className="fleet-status-line">
                {showAllApprovals
                  ? `${approvals.length} shown · ${approvals.filter((a) => a.status === 'pending').length} waiting`
                  : approvals.length === 0
                    ? 'Nothing waiting'
                    : `${approvals.length} waiting`}
              </p>
              <label className="checkbox inline">
                <input
                  type="checkbox"
                  checked={showAllApprovals}
                  onChange={(e) => setShowAllApprovals(e.target.checked)}
                />
                Show history
              </label>
            </header>
            {approvals.length === 0 ? (
              <p className="muted">Nothing waiting.</p>
            ) : (
              <div className="approval-card-list">
                {approvals.map((ap) => (
                  <ApprovalDecisionCard
                    key={ap.id}
                    approval={ap}
                    onApprove={async (id) => {
                      await approveApproval(id)
                      await load()
                    }}
                    onReject={async (id) => {
                      await rejectApproval(id)
                      setApprovals(await listApprovals(showAllApprovals ? undefined : 'pending'))
                    }}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {nav === 'users' && session.role === 'admin' && <UsersPanel />}

        {nav === 'activity' && (
          <>
            <header className="page-head">
              <p className="fleet-status-line">
                {agentActions.length === 0 ? 'No entries' : `${agentActions.length} entries`}
              </p>
            </header>
            <section className="panel">
              {agentActions.length === 0 ? (
                <p className="muted">No entries yet.</p>
              ) : (
                <AgentLogList items={agentActions} />
              )}
            </section>
          </>
        )}

        {nav !== 'chat' &&
          nav !== 'users' &&
          nav !== 'approvals' &&
          nav !== 'infrastructure' &&
          nav !== 'backupvault' &&
          nav !== 'email' &&
          nav !== 'voicemg' &&
          nav !== 'hosts' &&
          nav !== 'alerts' &&
          nav !== 'activity' && (
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
