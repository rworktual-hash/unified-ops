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

export type EmailSshSnapshot = {
  id: number
  server_id: number
  collected_at: string
  queue_messages: number | null
  queue_size_kb: number | null
  queue_active: number | null
  queue_deferred: number | null
  queue_hold: number | null
  postfix_active: boolean | null
  dovecot_active: boolean | null
  opendkim_active: boolean | null
  amavis_active: boolean | null
  clamav_active: boolean | null
  mail_received: number | null
  mail_delivered: number | null
  mail_bounced: number | null
  mail_rejected: number | null
  mail_deferred: number | null
  log_reject_lines: number | null
  log_bounce_lines: number | null
  log_amavis_lines: number | null
  log_spam_lines: number | null
  fail2ban_banned: number | null
  stats_source: string | null
  recent_log_sample: string | null
  collect_error: string | null
}

export type EmailSshOverview = {
  read_only: boolean
  source: string
  servers: {
    server_id: number
    server_name: string
    ip_address: string
    snapshot: EmailSshSnapshot | null
  }[]
  total_delivered: number | null
  total_bounced: number | null
  total_rejected: number | null
  total_deferred: number | null
  total_received: number | null
  note: string
}

export async function fetchEmailSshOverview(): Promise<EmailSshOverview> {
  const res = await apiFetch('/email/ssh-overview')
  if (!res.ok) throw new Error('Failed to load email SSH overview')
  return res.json()
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

export type BackupVaultSnapshot = {
  id: number
  server_id: number
  collected_at: string
  role: 'mysql' | 'postgres' | 'app'
  service_active: boolean | null
  docker_active: boolean | null
  nginx_active: boolean | null
  cron_active: boolean | null
  containers_running: number | null
  container_summary: string | null
  replication_io_running: boolean | null
  replication_sql_running: boolean | null
  replica_in_recovery: boolean | null
  replication_lag_seconds: number | null
  db_connections: number | null
  slow_queries: number | null
  db_uptime_seconds: number | null
  data_mount: string | null
  data_disk_used_pct: number | null
  data_disk_free_gb: number | null
  latest_backup_at: string | null
  latest_backup_path: string | null
  latest_backup_size_bytes: number | null
  backup_file_count: number | null
  backup_total_size_bytes: number | null
  backup_process_count: number | null
  extra_service_status: string | null
  healthcheck_status: string | null
  collect_error: string | null
}

export type BackupVaultOverview = {
  read_only: boolean
  source: string
  servers: {
    server_id: number
    server_name: string
    ip_address: string
    server_type: string | null
    snapshot: BackupVaultSnapshot | null
  }[]
  total_hosts: number
  collected_hosts: number
  replication_healthy: number
  replication_unhealthy: number
  storage_warning: number
  stale_backup_hosts: number
  note: string
}

export async function fetchBackupVaultOverview(): Promise<BackupVaultOverview> {
  const res = await apiFetch('/backupvault/ssh-overview')
  if (!res.ok) throw new Error('Failed to load BackupVault SSH overview')
  return res.json()
}

export type InfrastructureSnapshot = {
  id: number
  server_id: number
  collected_at: string
  role: string
  service_active: boolean | null
  nginx_active: boolean | null
  kong_active: boolean | null
  docker_active: boolean | null
  redis_role: string | null
  redis_connected_clients: number | null
  redis_used_memory_bytes: number | null
  replication_io_running: boolean | null
  replication_sql_running: boolean | null
  replica_in_recovery: boolean | null
  replication_lag_seconds: number | null
  db_connections: number | null
  slow_queries: number | null
  db_uptime_seconds: number | null
  data_mount: string | null
  data_disk_used_pct: number | null
  data_disk_free_gb: number | null
  extra_service_status: string | null
  healthcheck_status: string | null
  collect_error: string | null
}

export type InfrastructureOverview = {
  read_only: boolean
  source: string
  servers: {
    server_id: number
    server_name: string
    ip_address: string
    server_type: string | null
    snapshot: InfrastructureSnapshot | null
  }[]
  total_hosts: number
  collected_hosts: number
  service_down: number
  storage_warning: number
  replication_healthy: number
  replication_unhealthy: number
  note: string
}

export async function fetchInfrastructureOverview(): Promise<InfrastructureOverview> {
  const res = await apiFetch('/infrastructure/ssh-overview')
  if (!res.ok) throw new Error('Failed to load infrastructure SSH overview')
  return res.json()
}

export type VoiceMgSnapshot = {
  id: number
  server_id: number
  collected_at: string
  role: string
  service_active: boolean | null
  docker_active: boolean | null
  nginx_active: boolean | null
  containers_running: number | null
  container_summary: string | null
  app_process_count: number | null
  app_process_sample: string | null
  gpu_device_count: number | null
  gpu_util_summary: string | null
  data_mount: string | null
  data_disk_used_pct: number | null
  data_disk_free_gb: number | null
  extra_service_status: string | null
  healthcheck_status: string | null
  collect_error: string | null
}

export type VoiceMgOverview = {
  read_only: boolean
  source: string
  servers: {
    server_id: number
    server_name: string
    ip_address: string
    server_type: string | null
    snapshot: VoiceMgSnapshot | null
  }[]
  total_hosts: number
  collected_hosts: number
  vmg_hosts: number
  stt_hosts: number
  service_down: number
  storage_warning: number
  note: string
}

export async function fetchVoiceMgOverview(): Promise<VoiceMgOverview> {
  const res = await apiFetch('/voicemg/ssh-overview')
  if (!res.ok) throw new Error('Failed to load VoiceMG SSH overview')
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

export type LegacyStreamStatus = {
  domain: string
  enabled: boolean
  configured: boolean
  database: string | null
  table: string
  metric_cols: string[]
  row_count: number
  last_source_id: number
  last_synced_at: string | null
  last_error: string | null
}

export type LegacyStatus = {
  configured: boolean
  connection_ok: boolean
  connection_error?: string | null
  scheduled_sync_enabled: boolean
  streams: LegacyStreamStatus[]
}

export type LegacyOverview = {
  domain: string
  period_hours: number
  point_count: number
  distinct_hosts: number
  status_counts: Record<string, number>
  averages: Record<string, number>
  latest_by_server: {
    server_id: number | null
    server_name: string
    ip_address: string | null
    latest_at: string
    metrics: Record<string, number | string | null>
  }[]
}

export async function fetchLegacyStatus(): Promise<LegacyStatus> {
  const res = await apiFetch('/legacy-metrics/status')
  if (!res.ok) throw new Error('Failed to load legacy metrics status')
  return res.json()
}

export async function fetchLegacyOverview(
  domain: string,
  hours = 24,
): Promise<LegacyOverview> {
  const res = await apiFetch(`/legacy-metrics/overview/${domain}?hours=${hours}`)
  if (!res.ok) throw new Error('Failed to load legacy overview')
  return res.json()
}

export type BackupVaultRun = {
  id: number
  target_id: number | null
  target_name: string
  db_type: string | null
  target_host: string | null
  backup_type: string | null
  trigger_type: string | null
  status: string | null
  started_at: string | null
  completed_at: string | null
  file_size_bytes: number | null
  file_size_label: string | null
  file_path: string | null
  error_message: string | null
  duration_seconds: number | null
  destination_count: number
}

export type BackupVaultRunHistory = {
  ok: boolean
  source?: string | null
  database?: string | null
  reason?: string | null
  total: number
  success_rate: number
  success: number
  failed: number
  partial: number
  running: number
  pending: number
  runs: BackupVaultRun[]
}

export async function fetchBackupVaultRuns(): Promise<BackupVaultRunHistory> {
  const res = await apiFetch('/legacy-metrics/backupvault/runs')
  if (!res.ok) throw new Error('Failed to load BackupVault run history')
  return res.json()
}

export async function syncLegacyMetrics(domain?: string): Promise<{ ok: boolean; results: unknown[] }> {
  const path = domain ? `/legacy-metrics/sync/${domain}` : '/legacy-metrics/sync'
  const res = await apiFetch(path, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Legacy sync failed')
  }
  return res.json()
}
