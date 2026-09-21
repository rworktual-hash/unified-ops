import { apiPath } from './apiBase'
import { authHeaders, setStoredToken } from './authStorage'
import type {
  AgentAction,
  Alert,
  Approval,
  InvestigationResult,
  LiveAlert,
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

export type EmailExtraSender = {
  sender: string
  count: number
}

export type EmailExtraTotals = {
  sent: number
  bounce: number
  deferred: number
  host_not_reachable: number
  delivered: number
  inbound: number
  outbound: number
  failed: number
  blocked: number
  spam: number
  quarantine: number
  campaign_queued: number
  log_total: number
}

export type EmailExtraQueue = {
  queue_count: number
  deferred_count: number
  active_count: number
  incoming_count: number
  snapshot_at: string | null
}

export type EmailExtraServer = {
  server: string | null
  server_name: string | null
  inventory_name: string | null
  queue_count: number
  deferred_count: number
  active_count: number
  incoming_count: number
  snapshot_at: string | null
  top_senders: EmailExtraSender[]
}

export type EmailExtraEvent = {
  id: number
  occurred_at: string | null
  event_type: string | null
  direction: string | null
  from_addr: string | null
  to_addr: string | null
  subject: string | null
  status: string | null
  dsn: string | null
  reason: string | null
  queue_id: string | null
  message_id: string | null
  spam_score: number | null
  dkim_result: string | null
  spf_result: string | null
  classification: string | null
  server: string | null
  server_name: string | null
  inventory_name: string | null
}

export type EmailExtras = {
  ok: boolean
  database: string | null
  reason: string | null
  period_hours: number
  totals: EmailExtraTotals
  queue: EmailExtraQueue
  servers: EmailExtraServer[]
  events: EmailExtraEvent[]
}

export async function fetchEmailExtras(hours = 24): Promise<EmailExtras> {
  const res = await apiFetch(`/email/extras?hours=${hours}`)
  if (!res.ok) throw new Error('Failed to load email extras')
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

export type ApprovalCatalog = {
  safe_actions: string[]
  restart_services: string[]
}

export async function fetchApprovalCatalog(): Promise<ApprovalCatalog> {
  const res = await apiFetch('/approvals/catalog')
  if (!res.ok) throw new Error('Failed to load approval catalog')
  return res.json()
}

export async function createApproval(payload: {
  server_id: number
  action_key: string
  action_params?: Record<string, string> | null
  alert_id?: number | null
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
    body: JSON.stringify({ decided_by: 'operator', confirmed: true }),
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

export async function listLiveAlerts(): Promise<{
  ok: boolean
  reason: string | null
  alerts: LiveAlert[]
}> {
  const res = await apiFetch('/alerts/live')
  if (!res.ok) throw new Error('Failed to load live .222 alerts')
  return res.json()
}

export async function investigateLiveAlert(sourceId: number): Promise<InvestigationResult> {
  const res = await apiFetch(`/alerts/live/${sourceId}/investigate`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || 'Investigation failed')
  }
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
  dest_types?: string | null
  log_excerpt?: string | null
}

export type BackupVaultTarget = {
  id: number
  name: string
  db_type: string | null
  host: string | null
  port: number | null
  database_name: string | null
  description: string | null
  is_active: boolean
  last_status: string | null
  last_started_at: string | null
}

export type BackupVaultNfsServer = {
  id: number
  name: string
  host: string | null
  export_path: string | null
  mount_point: string | null
  description: string | null
  role: string | null
  is_active: boolean
  status: string | null
  disk_size: string | null
  disk_used: string | null
  disk_avail: string | null
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

export async function fetchBackupVaultRuns(start?: string, end?: string): Promise<BackupVaultRunHistory> {
  const params = new URLSearchParams()
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  const suffix = params.toString() ? `?${params}` : ''
  const res = await apiFetch(`/legacy-metrics/backupvault/runs${suffix}`)
  if (!res.ok) throw new Error('Failed to load BackupVault run history')
  return res.json()
}

export type BackupVaultDashboard = {
  ok: boolean
  reason?: string | null
  checked_at?: string | null
  live_db_servers: number
  today_runs: number
  today_success: number
  today_failed: number
  failures_30d: number
  primary_nfs_pct: number | null
  primary_nfs_used: string | null
  primary_nfs_size: string | null
  data_backed_up_bytes: number | null
  data_backed_up_label: string | null
  remote_used: string | null
  remote_size: string | null
  remote_pct: number | null
  s3_bytes: number | null
  s3_label: string | null
  s3_objects: number | null
  calendar: Array<{
    date: string
    tone: string
    success: number
    failed: number
    partial: number
    total: number
  }>
  history_14d: Array<{ date: string; runs: number }>
}

export async function fetchBackupVaultDashboard(): Promise<BackupVaultDashboard> {
  const res = await apiFetch('/legacy-metrics/backupvault/dashboard')
  if (!res.ok) throw new Error('Failed to load BackupVault dashboard')
  return res.json()
}

export type BackupVaultIncrementalJob = {
  id: number
  name: string
  script: string | null
  status: string | null
  last_success: string | null
  file_size_bytes: number | null
  file_size_label: string | null
  remote_path: string | null
  host: string | null
  schedule: string | null
}

export type BackupVaultIncremental = {
  ok: boolean
  reason?: string | null
  source?: string | null
  host: string | null
  schedule: string | null
  last_cycle: string | null
  jobs: BackupVaultIncrementalJob[]
}

export async function fetchBackupVaultIncremental(): Promise<BackupVaultIncremental> {
  const res = await apiFetch('/legacy-metrics/backupvault/incremental')
  if (!res.ok) throw new Error('Failed to load incremental backups')
  return res.json()
}

export type BackupVaultRepoFolder = {
  name: string
  dest: string
  latest_file: string | null
  file_path: string | null
  file_size_bytes: number | null
  file_size_label: string | null
  modified_at: string | null
  file_count: number
}

export type BackupVaultRepoTier = {
  id: string
  label: string
  folder_count: number
  file_count: number
  bytes_label: string | null
  folders: BackupVaultRepoFolder[]
}

export async function fetchBackupVaultRepositories(): Promise<{
  ok: boolean
  reason?: string | null
  source?: string | null
  tiers: BackupVaultRepoTier[]
}> {
  const res = await apiFetch('/legacy-metrics/backupvault/repositories')
  if (!res.ok) throw new Error('Failed to load BackupVault repositories')
  return res.json()
}

export async function fetchBackupVaultTargets(): Promise<{
  ok: boolean
  reason?: string | null
  targets: BackupVaultTarget[]
}> {
  const res = await apiFetch('/legacy-metrics/backupvault/targets')
  if (!res.ok) throw new Error('Failed to load BackupVault targets')
  return res.json()
}

export async function fetchBackupVaultNfs(): Promise<{
  ok: boolean
  reason?: string | null
  servers: BackupVaultNfsServer[]
}> {
  const res = await apiFetch('/legacy-metrics/backupvault/nfs')
  if (!res.ok) throw new Error('Failed to load BackupVault NFS servers')
  return res.json()
}

export type BackupVaultMonDb = {
  id: number
  name: string
  host: string | null
  port: number | null
  db_type: string | null
  environment: string | null
  ha_role: string | null
  ha_group: string | null
  snapshot_at: string | null
  cpu_pct: number | null
  mem_pct: number | null
  disk_pct: number | null
  load_avg_1: number | null
  connections: number | null
  active_queries: number | null
  qps: number | null
  disk_used: string | null
  mem_used_mb: number | null
  mem_total_mb: number | null
}

export type BackupVaultMonNfs = {
  id: number
  name: string
  host: string | null
  export_path: string | null
  mount_point: string | null
  role: string | null
  status: string | null
  disk_size: string | null
  disk_used: string | null
  disk_avail: string | null
  disk_pct: number | null
  inode_pct: number | null
  snapshot_at: string | null
}

export type BackupVaultStorageTile = {
  id: number
  name: string
  role: string | null
  host: string | null
  path: string | null
  disk_size: string | null
  disk_used: string | null
  disk_avail: string | null
  disk_pct: number | null
}

export type BackupVaultMonitoring = {
  ok: boolean
  reason?: string | null
  db_count: number
  nfs_count: number
  db_with_snapshot: number
  db_servers: BackupVaultMonDb[]
  nfs_servers: BackupVaultMonNfs[]
  storage: BackupVaultStorageTile[]
}

export async function fetchBackupVaultMonitoring(): Promise<BackupVaultMonitoring> {
  const res = await apiFetch('/legacy-metrics/backupvault/monitoring')
  if (!res.ok) throw new Error('Failed to load BackupVault monitoring')
  return res.json()
}

export type InventoryBaremetal = {
  id: number
  order_id: string | null
  server_id: string | null
  hostname: string | null
  host_public_ip: string | null
  ilo_private_ip: string | null
  cluster: string | null
  cluster_group: string | null
  os: string | null
  engineer: string | null
  ram: string | null
  cpu: string | null
  location: string | null
  status: string | null
  notes: string | null
}

export type InventoryCluster = {
  id: number
  cluster_name: string
  cluster_label: string | null
  description: string | null
  total_nodes: number
  total_cpu: number | null
  total_ram_gb: number | null
  total_storage_gb: number | null
  total_vms: number
  used_cpu: number | null
  used_ram_gb: number | null
  used_storage_gb: number | null
  cpu_pct: number | null
  ram_pct: number | null
  storage_pct: number | null
}

export type InventoryHost = {
  id: number
  node_name: string
  cluster_id: number | null
  cluster_name: string | null
  cluster_label: string | null
  host_public_ip: string | null
  host_private_ip: string | null
  total_cpu: number | null
  used_cpu: number | null
  total_ram_gb: number | null
  used_ram_gb: number | null
  total_storage_gb: number | null
  used_storage_gb: number | null
  cpu_pct: number | null
  ram_pct: number | null
  storage_pct: number | null
  status: string | null
  uptime_seconds: number | null
  updated_at: string | null
}

export type InventoryVm = {
  id: number
  vm_id: string
  node_name: string | null
  cluster_name: string | null
  guest_hostname: string | null
  guest_ip_private: string | null
  guest_ip_public: string | null
  guest_ip_ipv6: string | null
  services: string | null
  team: string | null
  status: string | null
  cpu: number | null
  ram_gb: number | null
  disk_gb: number | null
  cpu_util_pct: number | null
  ram_used_gb: number | null
  ram_total_gb: number | null
  storage_used_gb: number | null
  net_in_bps: number | null
  net_out_bps: number | null
  updated_at: string | null
}

export type InventoryDashboard = {
  total_servers: number
  online_servers: number
  total_vms: number
  active_vms: number
  baremetal_count: number
  host_count: number
  cluster_count: number
  cpu_total: number | null
  cpu_used: number | null
  cpu_pct: number | null
  ram_total_gb: number | null
  ram_used_gb: number | null
  ram_pct: number | null
  storage_total_gb: number | null
  storage_used_gb: number | null
  storage_pct: number | null
}

export type InventoryPortal = {
  ok: boolean
  database?: string | null
  reason?: string | null
  dashboard: InventoryDashboard
  clusters: InventoryCluster[]
  hosts: InventoryHost[]
  baremetal: InventoryBaremetal[]
  vms: InventoryVm[]
}

export async function fetchInventoryPortal(): Promise<InventoryPortal> {
  const res = await apiFetch('/legacy-metrics/inventory')
  if (!res.ok) throw new Error('Failed to load server inventory')
  return res.json()
}

export type InventoryDid = {
  id: number
  did_number: string
  country_code: string | null
  area_code: string | null
  number_type: string | null
  status: string | null
  provider: string | null
  client: string | null
  use_case: string | null
  application: string | null
  monthly_cost: number | null
  purchase_date: string | null
  allocated_date: string | null
}

export type InventorySsl = {
  id: number
  hostname: string
  domain: string | null
  issuer: string | null
  valid_from: string | null
  valid_to: string | null
  remaining_days: number | null
  status: string | null
  serial_number: string | null
  last_checked: string | null
}

export type InventoryDomain = {
  id: number
  domain_name: string
  registrar: string | null
  renewal_date: string | null
  team: string | null
  status: string | null
  notes: string | null
}

export type InventoryCatalog = {
  ok: boolean
  database?: string | null
  reason?: string | null
  did_total: number
  did_allocated: number
  ssl_total: number
  ssl_expiring: number
  domain_total: number
  dids: InventoryDid[]
  ssl: InventorySsl[]
  domains: InventoryDomain[]
  providers: Array<{ id: number; provider_name?: string | null; support_email?: string | null }>
  clients: Array<{ id: number; company_name?: string | null; contact_email?: string | null; status?: string | null }>
}

export async function fetchInventoryCatalog(): Promise<InventoryCatalog> {
  const res = await apiFetch('/legacy-metrics/inventory/catalog')
  if (!res.ok) throw new Error('Failed to load DID / SSL / domain catalog')
  return res.json()
}

export type AiInsightExtraTile = {
  key: string
  label: string
  value: string
}

export type AiInsightExtra = {
  id: number
  server_name: string
  ip_address: string
  hostname: string | null
  group: string | null
  group_id: string | null
  server_type: string | null
  health_score: number | null
  health_status: string | null
  cpu_utilization: number | null
  memory_utilization: number | null
  storage_utilization: number | null
  load_average: number | null
  gpu_utilization: number | null
  gpu_temperature: number | null
  open_alerts: number
  recorded_at: string | null
  extras: AiInsightExtraTile[]
}

export type AiInsightExtras = {
  ok: boolean
  database?: string | null
  reason?: string | null
  servers: AiInsightExtra[]
}

export async function fetchAiInsightExtras(): Promise<AiInsightExtras> {
  const res = await apiFetch('/legacy-metrics/ai-insights/extras')
  if (!res.ok) throw new Error('Failed to load AI Insights extras')
  return res.json()
}

export function matchAiInsightExtra(
  extras: AiInsightExtra[] | undefined,
  ip: string,
  name?: string,
): AiInsightExtra | undefined {
  if (!extras?.length) return undefined
  const ipMatch = extras.find((row) => row.ip_address && row.ip_address === ip)
  if (ipMatch) return ipMatch
  if (!name) return undefined
  const needle = name.toLowerCase()
  return extras.find(
    (row) =>
      row.server_name.toLowerCase() === needle ||
      (row.hostname ?? '').toLowerCase() === needle,
  )
}

export type VoiceMgExtra = {
  id: number
  hostname: string
  ip: string
  ip_address: string
  product: string | null
  role: string | null
  group: string | null
  cpu_pct: number | null
  load1: number | null
  mem_used_mb: number | null
  mem_total_mb: number | null
  mem: string | null
  mem_pct: number | null
  active_calls: number | null
  rtp_sessions: number | null
  rtp_mbps_out: number | null
  rtp_mbps_in: number | null
  rtp_mbps_exp: number | null
  jitter_ms: number | null
  pkts_lost_delta: number | null
  pkts_sent_ps: number | null
  pkts_recv_ps: number | null
  packet_loss_pct: number | null
  mos: number | null
  stall: number | null
  udp_active: number | null
  udp_inactive: number | null
  quality_source: string | null
  rtcp: string | null
  disk_used_pct: number | null
  disk_mount: string | null
  rx_errors?: number | null
  rx_drops?: number | null
  open_fds?: number | null
  threads?: number | null
  ipc_sent_ps?: number | null
  ipc_recv_ps?: number | null
  ipc_latency_ms?: number | null
  runqueue?: number | null
  buffers_mb?: number | null
  cached_mb?: number | null
  udp_pps_in?: number | null
  udp_pps_out?: number | null
  nic_rx_mbps?: number | null
  nic_tx_mbps?: number | null
  proc_cpu_pct?: number | null
  proc_mem_pct?: number | null
  udp_sockets?: number | null
  rtp_gb?: number | null
  recorded_at: string | null
}

export type VoiceMgExtras = {
  ok: boolean
  database?: string | null
  reason?: string | null
  servers: VoiceMgExtra[]
}

export async function fetchVoiceMgExtras(): Promise<VoiceMgExtras> {
  const res = await apiFetch('/legacy-metrics/voicemg/extras', {
    signal: AbortSignal.timeout(8000),
  })
  if (!res.ok) throw new Error('Failed to load VoiceMG extras')
  return res.json()
}

export type VoiceMgHistoryRange =
  | 'live'
  | '5m'
  | '30m'
  | '1h'
  | '2h'
  | '6h'
  | '12h'
  | 'today'
  | 'yesterday'
  | '2d'
  | 'week'
  | 'custom'
export type VoiceMgHistoryGroup = 'all' | 'ai_ccaas' | 'ccaas'

export type VoiceMgHistoryPoint = {
  ts: string
  active_calls: number | null
  mos: number | null
  jitter_ms: number | null
  packet_loss_pct: number | null
  rtp_mbps: number | null
  rtp_mbps_in?: number | null
  rtp_mbps_out?: number | null
  rtp_mbps_exp?: number | null
  cpu_pct: number | null
  mem_pct?: number | null
  rx_errors?: number | null
  rx_drops?: number | null
  open_fds?: number | null
  threads?: number | null
  ipc_sent_ps?: number | null
  ipc_recv_ps?: number | null
  ipc_latency_ms?: number | null
  runqueue?: number | null
  buffers_mb?: number | null
  cached_mb?: number | null
  udp_pps_in?: number | null
  udp_pps_out?: number | null
  nic_rx_mbps?: number | null
  nic_tx_mbps?: number | null
  proc_cpu_pct?: number | null
  proc_mem_pct?: number | null
  udp_sockets?: number | null
  rtp_gb?: number | null
  disk_used_pct?: number | null
}

export type VoiceMgHistory = {
  ok: boolean
  database?: string | null
  reason?: string | null
  range: VoiceMgHistoryRange | string
  group: VoiceMgHistoryGroup | string
  since: string | null
  until?: string | null
  bucket_seconds: number
  host_count: number
  point_count: number
  points: VoiceMgHistoryPoint[]
  server_id?: number | null
  host_name?: string | null
}

export async function fetchVoiceMgHistory(
  range: VoiceMgHistoryRange,
  group: VoiceMgHistoryGroup,
  start?: string,
  end?: string,
  serverId?: number | null,
): Promise<VoiceMgHistory> {
  const params = new URLSearchParams({ range, group })
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  if (serverId != null) params.set('server_id', String(serverId))
  const res = await apiFetch(`/legacy-metrics/voicemg/history?${params}`, {
    signal: AbortSignal.timeout(15000),
  })
  if (!res.ok) throw new Error('Failed to load VoiceMG history')
  return res.json()
}

export function matchVoiceMgExtra(
  extras: VoiceMgExtra[] | undefined,
  ip: string,
  name?: string,
): VoiceMgExtra | undefined {
  if (!extras?.length) return undefined
  const ipMatch = extras.find((row) => (row.ip_address || row.ip) === ip)
  if (ipMatch) return ipMatch
  if (!name) return undefined
  const needle = name.toLowerCase()
  return extras.find((row) => row.hostname.toLowerCase() === needle)
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
