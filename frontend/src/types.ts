export type ConnectionTestResult = {
  success: boolean
  message: string
  latency_ms: number | null
}

export type SshAuthMode = 'auto' | 'key' | 'password'

export type Server = {
  id: number
  server_name: string
  ip_address: string
  ssh_port: number
  ssh_username: string
  credential_ref: string | null
  ssh_auth_mode: SshAuthMode
  has_ssh_password: boolean
  server_type: string | null
  project: string | null
  is_active: boolean
}

export type ServerCreate = Omit<Server, 'id' | 'has_ssh_password'> & {
  ssh_password?: string | null
}

export type ServerMetric = {
  id: number
  server_id: number
  collected_at: string
  load_1m: number | null
  mem_used_pct: number | null
  disk_root_pct: number | null
  collect_error: string | null
}

export type GpuMetric = {
  id: number
  server_id: number
  collected_at: string
  gpu_index: number
  utilization_pct: number | null
  mem_used_mb: number | null
  mem_total_mb: number | null
  mem_used_pct: number | null
  temperature_c: number | null
  power_w: number | null
  clock_mhz: number | null
  status: string
  collect_error: string | null
}

export type GpuInsightsSnapshot = {
  id: number
  server_id: number
  collected_at: string
  process_count: number | null
  tcp_inuse: number | null
  tcp_connection_lines: number | null
  tcp_established: number | null
  listen_sockets: number | null
  listen_port_8000: number | null
  cpu_util_pct: number | null
  gpu_util_avg: number | null
  gpu_temp_avg: number | null
  net_rx_bytes: number | null
  net_tx_bytes: number | null
  collect_error: string | null
}

export type GpuProductSnapshot = {
  id: number
  server_id: number
  collected_at: string
  compute_process_count: number | null
  compute_mem_used_mb: number | null
  compute_process_names: string | null
  docker_containers_running: number | null
  gpu_model_name: string | null
  driver_version: string | null
  collect_error: string | null
}

export type MetricsBundle = {
  host: ServerMetric[]
  gpu: GpuMetric[]
  gpu_latest?: GpuMetric[]
  gpu_product?: GpuProductSnapshot | null
  gpu_insights?: GpuInsightsSnapshot | null
}

export type AgentAction = {
  id: number
  server_id: number
  alert_id: number | null
  action_type: string
  status: string
  summary: string
  diagnosis: string
  recommendation: string
  tool_trace: string | null
  created_at: string
}

export type Approval = {
  id: number
  server_id: number
  alert_id: number | null
  action_key: string
  action_params: string | null
  status: string
  request_notes: string | null
  requested_by: string
  decided_by: string | null
  execution_result: string | null
  created_at: string
  decided_at: string | null
  executed_at: string | null
  server_name: string
  ip_address: string
}

export type InvestigationResult = {
  agent_action_id: number
  summary: string
  diagnosis: string
  recommendation: string
}

export type Alert = {
  id: number
  server_id: number
  alert_type: string
  severity: string
  status: string
  title: string
  message: string
  first_seen_at: string
  last_seen_at: string
  resolved_at: string | null
  server_name: string
  ip_address: string
}
