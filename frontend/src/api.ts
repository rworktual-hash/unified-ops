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
  const res = await fetch(input, { ...init, headers })
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
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    let detail = 'Invalid email or password'
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* ignore */
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

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch('/health')
  if (!res.ok) throw new Error('Health check failed')
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
