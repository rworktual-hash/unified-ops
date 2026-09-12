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

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch('/health')
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function listServers(): Promise<Server[]> {
  const res = await fetch('/servers')
  if (!res.ok) throw new Error('Failed to load servers')
  return res.json()
}

export type ConnectionTestResult = {
  success: boolean
  message: string
  latency_ms: number | null
}

export async function testServerConnection(serverId: number): Promise<ConnectionTestResult> {
  const res = await fetch(`/servers/${serverId}/test-connection`, { method: 'POST' })
  const body = (await res.json()) as ConnectionTestResult
  if (!res.ok) {
    throw new Error(typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Test failed')
  }
  return body
}

export async function collectServerMetrics(serverId: number): Promise<MetricsBundle> {
  const res = await fetch(`/servers/${serverId}/collect-metrics`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Collect failed')
  }
  return res.json()
}

export async function fetchServerMetrics(serverId: number, limit = 5): Promise<MetricsBundle> {
  const res = await fetch(`/servers/${serverId}/metrics?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to load metrics')
  return res.json()
}

export async function sendChatMessage(
  message: string,
  serverId: number | null,
  signal?: AbortSignal,
): Promise<{ reply: string; servers_in_context: string[] }> {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: jsonHeaders,
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
  const res = await fetch(`/approvals${q}`)
  if (!res.ok) throw new Error('Failed to load approvals')
  return res.json()
}

export async function createApproval(payload: {
  server_id: number
  action_key: string
  action_params?: Record<string, string> | null
  request_notes?: string | null
}): Promise<Approval> {
  const res = await fetch('/approvals', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Failed to create approval')
  }
  return res.json()
}

export async function approveApproval(id: number): Promise<Approval> {
  const res = await fetch(`/approvals/${id}/approve`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ decided_by: 'operator' }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Approve failed')
  }
  return res.json()
}

export async function rejectApproval(id: number): Promise<Approval> {
  const res = await fetch(`/approvals/${id}/reject`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ decided_by: 'operator' }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Reject failed')
  }
  return res.json()
}

export async function listAgentActions(limit = 20): Promise<AgentAction[]> {
  const res = await fetch(`/agent-actions?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to load agent actions')
  return res.json()
}

export async function investigateAlert(alertId: number): Promise<InvestigationResult> {
  const res = await fetch(`/alerts/${alertId}/investigate`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Investigation failed')
  }
  return res.json()
}

export async function investigateServer(serverId: number): Promise<InvestigationResult> {
  const res = await fetch(`/servers/${serverId}/investigate`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Investigation failed')
  }
  return res.json()
}

export async function listAlerts(status?: string): Promise<Alert[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  const res = await fetch(`/alerts${q}`)
  if (!res.ok) throw new Error('Failed to load alerts')
  return res.json()
}

export async function resolveAlert(alertId: number): Promise<Alert> {
  const res = await fetch(`/alerts/${alertId}/resolve`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to resolve alert')
  return res.json()
}

export async function createServer(payload: ServerCreate): Promise<Server> {
  const res = await fetch('/servers', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Failed to create server')
  }
  return res.json()
}
