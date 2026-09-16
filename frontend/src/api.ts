import { apiPath } from './apiBase'
import { authHeaders, setStoredToken } from './authStorage'
import type {
  AgentAction,
  Alert,
  Approval,
  InvestigationResult,
  MetricsBundle,
  Server,
  ServerCreate,
} from './types'

const jsonHeaders = { 'Content-Type': 'application/json' }

export class UnauthorizedError extends Error {
  constructor() {
    super('Unauthorized')
    this.name = 'UnauthorizedError'
  }
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  const token = authHeaders().Authorization
  if (token) headers.set('Authorization', token)
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const url = typeof input === 'string' ? apiPath(input) : input
  const res = await fetch(url, { ...init, headers })
  if (res.status === 401) throw new UnauthorizedError()
  return res
}

export type AppUser = {
  id: number
  email: string
  role: string
  is_active: boolean
}

export async function login(email: string, password: string): Promise<AppUser> {
  const res = await fetch(apiPath('/auth/login'), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const text = await res.text()
    let detail =
      res.status === 401 ? 'Invalid email or password' : `Sign in failed (HTTP ${res.status})`
    try {
      const body = JSON.parse(text) as { detail?: string | { msg?: string }[] }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      if (text && text.length < 200 && !text.includes('<html')) detail = text
    }
    throw new Error(detail)
  }
  const data = (await res.json()) as { access_token: string }
  setStoredToken(data.access_token)
  return fetchMe()
}

export async function fetchMe(): Promise<AppUser> {
  const res = await apiFetch('/auth/me')
  if (!res.ok) throw new UnauthorizedError()
  return res.json()
}

export async function listUsers(): Promise<AppUser[]> {
  const res = await apiFetch('/users')
  if (!res.ok) throw new Error('Failed to load users')
  return res.json()
}

export async function createUser(payload: {
  email: string
  password: string
  role?: 'user' | 'admin'
}): Promise<AppUser> {
  const res = await apiFetch('/users', {
    method: 'POST',
    body: JSON.stringify({ role: 'user', ...payload }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Failed to create user')
  }
  return res.json()
}

export async function updateUser(
  userId: number,
  payload: { password?: string; is_active?: boolean },
): Promise<AppUser> {
  const res = await apiFetch(`/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Failed to update user')
  }
  return res.json()
}

export type EmailOverview = {
  period_hours: number
  total: number
  inbound: number
  outbound: number
  delivered: number
  bounced: number
  failed: number
  deferred?: number
  blocked?: number
  timed_out?: number
  wrong_hits?: number
  sync_configured: boolean
  scheduled_sync_enabled?: boolean
  read_only?: boolean
  last_source_id: number | null
  last_synced_at: string | null
  last_sync_error: string | null
}

export type EmailLogEvent = {
  id: number
  server_id: number | null
  occurred_at: string
  event_type: string | null
  direction: string | null
  from_addr: string | null
  to_addr: string | null
  subject: string | null
  status: string | null
  dsn: string | null
  queue_id: string | null
}

export type EmailQueueSnapshot = {
  id: number
  server_id: number
  collected_at: string
  queue_messages: number | null
  queue_size_kb: number | null
  postfix_active: boolean | null
  collect_error: string | null
}

export async function fetchEmailOverview(hours = 24): Promise<EmailOverview> {
  const res = await apiFetch(`/email/overview?hours=${hours}`)
  if (!res.ok) throw new Error('Failed to load email overview')
  return res.json()
}

export async function fetchEmailEvents(
  serverId?: number,
  hours?: number,
  search?: string,
  limit = 200,
): Promise<EmailLogEvent[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (serverId != null) params.set('server_id', String(serverId))
  if (hours != null) params.set('hours', String(hours))
  if (search) params.set('q', search)
  const res = await apiFetch(`/email/events?${params}`)
  if (!res.ok) throw new Error('Failed to load email events')
  return res.json()
}

export async function fetchEmailQueue(serverId: number): Promise<EmailQueueSnapshot | null> {
  const res = await apiFetch(`/email/servers/${serverId}/queue`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error('Failed to load mail queue')
  const text = await res.text()
  if (!text) return null
  return JSON.parse(text) as EmailQueueSnapshot
}

export async function syncEmailLogs(): Promise<{ ok: boolean; inserted?: number; error?: string }> {
  const res = await apiFetch('/email/sync', { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Sync failed')
  }
  return res.json()
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(apiPath('/health'))
  if (!res.ok) throw new Error(`Health check failed (HTTP ${res.status})`)
  const ct = res.headers.get('content-type') ?? ''
  if (!ct.includes('application/json')) {
    throw new Error('Health returned HTML — nginx is not proxying /health to the API')
  }
  const body = (await res.json()) as { status?: string }
  if (body.status !== 'ok') throw new Error('Health response unexpected')
  return body as { status: string }
}

export type FleetCollectStatus = {
  scheduled_collect_enabled: boolean
  interval_seconds: number
  last_run_at: string | null
  last_servers_ok: number | null
  last_servers_failed: number | null
  last_trigger: string | null
}

export async function fetchFleetCollectStatus(): Promise<FleetCollectStatus> {
  const res = await apiFetch('/fleet/collect-status')
  if (!res.ok) throw new Error('Failed to load fleet collect status')
  return res.json()
}

export async function collectAllServerMetrics(sync = true): Promise<{
  servers_collected: number
  servers_failed: number
  mode: string
}> {
  const q = sync ? '' : '?background=true'
  const res = await apiFetch(`/fleet/collect-metrics${q}`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Collect all failed')
  }
  return res.json()
}

export async function listServers(): Promise<Server[]> {
  const res = await apiFetch('/servers')
  if (!res.ok) throw new Error('Failed to load servers')
  return res.json()
}

export type ConnectionTestResult = {
  success: boolean
  message: string
  latency_ms: number | null
}

export async function testServerConnection(serverId: number): Promise<ConnectionTestResult> {
  const res = await apiFetch(`/servers/${serverId}/test-connection`, { method: 'POST' })
  const body = (await res.json()) as ConnectionTestResult
  if (!res.ok) {
    throw new Error(typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Test failed')
  }
  return body
}

export async function collectServerMetrics(serverId: number): Promise<MetricsBundle> {
  const res = await apiFetch(`/servers/${serverId}/collect-metrics`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Collect failed')
  }
  return res.json()
}

export async function fetchServerMetrics(serverId: number, limit = 5): Promise<MetricsBundle> {
  const res = await apiFetch(`/servers/${serverId}/metrics?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to load metrics')
  return res.json()
}

export type ServerMetricsHistory = {
  server_id: number
  hours: number
  host: import('./types').ServerMetric[]
  gpu: import('./types').GpuMetric[]
  gpu_insights: import('./types').GpuInsightsSnapshot[]
}

export async function fetchServerMetricsHistory(
  serverId: number,
  hours = 1,
): Promise<ServerMetricsHistory> {
  const res = await apiFetch(`/servers/${serverId}/metrics/history?hours=${hours}`)
  if (!res.ok) throw new Error('Failed to load metrics history')
  return res.json()
}

export async function sendChatMessage(
  message: string,
  serverId: number | null,
  signal?: AbortSignal,
): Promise<{ reply: string; servers_in_context: string[] }> {
  const res = await apiFetch('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, server_id: serverId }),
    signal,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Chat request failed')
  }
  return res.json()
}

export async function listApprovals(status?: string): Promise<Approval[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  const res = await apiFetch(`/approvals${q}`)
  if (!res.ok) throw new Error('Failed to load approvals')
  return res.json()
}

export async function createApproval(payload: {
  server_id: number
  action_key: string
  action_params?: Record<string, string> | null
  request_notes?: string | null
}): Promise<Approval> {
  const res = await apiFetch('/approvals', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Failed to create approval')
  }
  return res.json()
}

export async function approveApproval(id: number): Promise<Approval> {
  const res = await apiFetch(`/approvals/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ decided_by: 'operator' }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Approve failed')
  }
  return res.json()
}

export async function rejectApproval(id: number): Promise<Approval> {
  const res = await apiFetch(`/approvals/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ decided_by: 'operator' }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Reject failed')
  }
  return res.json()
}

export async function listAgentActions(limit = 20): Promise<AgentAction[]> {
  const res = await apiFetch(`/agent-actions?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to load agent actions')
  return res.json()
}

export async function investigateAlert(alertId: number): Promise<InvestigationResult> {
  const res = await apiFetch(`/alerts/${alertId}/investigate`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Investigation failed')
  }
  return res.json()
}

export async function investigateServer(serverId: number): Promise<InvestigationResult> {
  const res = await apiFetch(`/servers/${serverId}/investigate`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Investigation failed')
  }
  return res.json()
}

export async function listAlerts(status?: string): Promise<Alert[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  const res = await apiFetch(`/alerts${q}`)
  if (!res.ok) throw new Error('Failed to load alerts')
  return res.json()
}

export async function resolveAlert(alertId: number): Promise<Alert> {
  const res = await apiFetch(`/alerts/${alertId}/resolve`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to resolve alert')
  return res.json()
}

export async function createServer(payload: ServerCreate): Promise<Server> {
  const res = await apiFetch('/servers', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Failed to create server')
  }
  return res.json()
}
