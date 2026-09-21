from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LegacyStreamStatusRead(BaseModel):
    domain: str
    enabled: bool
    configured: bool
    database: str | None
    table: str
    metric_cols: list[str]
    row_count: int
    last_source_id: int
    last_synced_at: datetime | None
    last_error: str | None


class LegacyStatusRead(BaseModel):
    configured: bool
    connection_ok: bool
    connection_error: str | None = None
    scheduled_sync_enabled: bool
    streams: list[LegacyStreamStatusRead]


class LegacySyncResultRead(BaseModel):
    ok: bool
    results: list[dict]


class LegacyOverviewRead(BaseModel):
    domain: str
    period_hours: int
    point_count: int
    distinct_hosts: int
    status_counts: dict[str, int]
    averages: dict[str, float]
    latest_by_server: list[dict]


class BackupVaultRunRead(BaseModel):
    id: int
    target_id: int | None
    target_name: str
    db_type: str | None
    target_host: str | None
    backup_type: str | None
    trigger_type: str | None
    status: str | None
    started_at: datetime | None
    completed_at: datetime | None
    file_size_bytes: int | None
    file_size_label: str | None
    file_path: str | None
    error_message: str | None
    duration_seconds: int | None
    destination_count: int
    dest_types: str | None = None


class BackupVaultRunHistoryRead(BaseModel):
    ok: bool
    source: str | None = None
    database: str | None = None
    reason: str | None = None
    total: int = 0
    success_rate: int = 0
    success: int = 0
    failed: int = 0
    partial: int = 0
    running: int = 0
    pending: int = 0
    runs: list[BackupVaultRunRead]


class BackupVaultTargetRead(BaseModel):
    id: int
    name: str
    db_type: str | None
    host: str | None
    port: int | None
    database_name: str | None
    description: str | None
    is_active: bool
    last_status: str | None
    last_started_at: datetime | None


class BackupVaultTargetsRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    targets: list[BackupVaultTargetRead]


class BackupVaultNfsServerRead(BaseModel):
    id: int
    name: str
    host: str | None
    export_path: str | None
    mount_point: str | None
    description: str | None
    role: str | None
    is_active: bool
    status: str | None
    disk_size: str | None
    disk_used: str | None
    disk_avail: str | None


class BackupVaultMonDbRead(BaseModel):
    id: int
    name: str
    host: str | None
    port: int | None
    db_type: str | None
    environment: str | None
    ha_role: str | None
    ha_group: str | None
    snapshot_at: datetime | None
    cpu_pct: float | None
    mem_pct: float | None
    disk_pct: float | None
    load_avg_1: float | None
    connections: float | None
    active_queries: float | None
    qps: float | None
    disk_used: str | None
    mem_used_mb: float | None
    mem_total_mb: float | None


class BackupVaultMonNfsRead(BaseModel):
    id: int
    name: str
    host: str | None
    export_path: str | None
    mount_point: str | None
    role: str | None
    status: str | None
    disk_size: str | None
    disk_used: str | None
    disk_avail: str | None
    disk_pct: float | None
    inode_pct: float | None
    snapshot_at: datetime | None


class BackupVaultStorageTileRead(BaseModel):
    id: int
    name: str
    role: str | None
    host: str | None
    path: str | None
    disk_size: str | None
    disk_used: str | None
    disk_avail: str | None
    disk_pct: float | None


class BackupVaultMonitoringRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    db_count: int = 0
    nfs_count: int = 0
    db_with_snapshot: int = 0
    db_servers: list[BackupVaultMonDbRead]
    nfs_servers: list[BackupVaultMonNfsRead]
    storage: list[BackupVaultStorageTileRead]


class BackupVaultNfsRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    servers: list[BackupVaultNfsServerRead]


class InventoryBaremetalRead(BaseModel):
    id: int
    order_id: str | None = None
    server_id: str | None = None
    hostname: str | None = None
    host_public_ip: str | None = None
    ilo_private_ip: str | None = None
    cluster: str | None = None
    cluster_group: str | None = None
    os: str | None = None
    engineer: str | None = None
    ram: str | None = None
    cpu: str | None = None
    location: str | None = None
    status: str | None = None
    notes: str | None = None


class InventoryClusterRead(BaseModel):
    id: int
    cluster_name: str
    cluster_label: str | None = None
    description: str | None = None
    total_nodes: int = 0
    total_cpu: float | None = None
    total_ram_gb: float | None = None
    total_storage_gb: float | None = None
    total_vms: int = 0
    used_cpu: float | None = None
    used_ram_gb: float | None = None
    used_storage_gb: float | None = None
    cpu_pct: float | None = None
    ram_pct: float | None = None
    storage_pct: float | None = None


class InventoryHostRead(BaseModel):
    id: int
    node_name: str
    cluster_id: int | None = None
    cluster_name: str | None = None
    cluster_label: str | None = None
    host_public_ip: str | None = None
    host_private_ip: str | None = None
    total_cpu: float | None = None
    used_cpu: float | None = None
    total_ram_gb: float | None = None
    used_ram_gb: float | None = None
    total_storage_gb: float | None = None
    used_storage_gb: float | None = None
    cpu_pct: float | None = None
    ram_pct: float | None = None
    storage_pct: float | None = None
    status: str | None = None
    uptime_seconds: int | None = None
    updated_at: datetime | None = None


class InventoryVmRead(BaseModel):
    id: int
    vm_id: str
    node_name: str | None = None
    cluster_name: str | None = None
    guest_hostname: str | None = None
    guest_ip_private: str | None = None
    guest_ip_public: str | None = None
    guest_ip_ipv6: str | None = None
    services: str | None = None
    team: str | None = None
    status: str | None = None
    cpu: int | None = None
    ram_gb: float | None = None
    disk_gb: float | None = None
    cpu_util_pct: float | None = None
    ram_used_gb: float | None = None
    ram_total_gb: float | None = None
    storage_used_gb: float | None = None
    net_in_bps: float | None = None
    net_out_bps: float | None = None
    updated_at: datetime | None = None


class InventoryDashboardRead(BaseModel):
    total_servers: int = 0
    online_servers: int = 0
    total_vms: int = 0
    active_vms: int = 0
    baremetal_count: int = 0
    host_count: int = 0
    cluster_count: int = 0
    cpu_total: float | None = None
    cpu_used: float | None = None
    cpu_pct: float | None = None
    ram_total_gb: float | None = None
    ram_used_gb: float | None = None
    ram_pct: float | None = None
    storage_total_gb: float | None = None
    storage_used_gb: float | None = None
    storage_pct: float | None = None


class InventoryPortalRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    dashboard: InventoryDashboardRead
    clusters: list[InventoryClusterRead]
    hosts: list[InventoryHostRead]
    baremetal: list[InventoryBaremetalRead]
    vms: list[InventoryVmRead]


class InventoryDidRead(BaseModel):
    id: int
    did_number: str
    country_code: str | None = None
    area_code: str | None = None
    number_type: str | None = None
    status: str | None = None
    provider: str | None = None
    client: str | None = None
    use_case: str | None = None
    application: str | None = None
    monthly_cost: float | None = None
    purchase_date: datetime | date | None = None
    allocated_date: datetime | date | None = None


class InventorySslRead(BaseModel):
    id: int
    hostname: str
    domain: str | None = None
    issuer: str | None = None
    valid_from: datetime | date | None = None
    valid_to: datetime | date | None = None
    remaining_days: int | None = None
    status: str | None = None
    serial_number: str | None = None
    last_checked: datetime | date | None = None


class InventoryDomainRead(BaseModel):
    id: int
    domain_name: str
    registrar: str | None = None
    renewal_date: datetime | date | None = None
    team: str | None = None
    status: str | None = None
    notes: str | None = None


class InventoryNamedRead(BaseModel):
    id: int
    provider_name: str | None = None
    company_name: str | None = None
    company_id: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_person: str | None = None
    support_email: str | None = None
    support_phone: str | None = None
    status: str | None = None


class InventoryCatalogRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    did_total: int = 0
    did_allocated: int = 0
    ssl_total: int = 0
    ssl_expiring: int = 0
    domain_total: int = 0
    dids: list[InventoryDidRead]
    ssl: list[InventorySslRead]
    domains: list[InventoryDomainRead]
    providers: list[InventoryNamedRead]
    clients: list[InventoryNamedRead]


class AiInsightExtraTileRead(BaseModel):
    key: str
    label: str
    value: str


class AiInsightExtraRead(BaseModel):
    id: int
    server_name: str
    ip_address: str
    hostname: str | None = None
    group: str | None = None
    group_id: str | None = None
    server_type: str | None = None
    health_score: int | None = None
    health_status: str | None = None
    cpu_utilization: float | None = None
    memory_utilization: float | None = None
    storage_utilization: float | None = None
    load_average: float | None = None
    gpu_utilization: float | None = None
    gpu_temperature: float | None = None
    open_alerts: int = 0
    recorded_at: datetime | None = None
    extras: list[AiInsightExtraTileRead]


class AiInsightExtrasRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    servers: list[AiInsightExtraRead]


class VoiceMgExtraRead(BaseModel):
    id: int
    hostname: str
    ip: str
    ip_address: str
    product: str | None = None
    role: str | None = None
    group: str | None = None
    cpu_pct: float | None = None
    load1: float | None = None
    mem_used_mb: float | None = None
    mem_total_mb: float | None = None
    mem: str | None = None
    mem_pct: float | None = None
    active_calls: int | None = None
    rtp_sessions: int | None = None
    rtp_mbps_out: float | None = None
    rtp_mbps_in: float | None = None
    rtp_mbps_exp: float | None = None
    jitter_ms: float | None = None
    pkts_lost_delta: float | None = None
    pkts_sent_ps: float | None = None
    pkts_recv_ps: float | None = None
    packet_loss_pct: float | None = None
    mos: float | None = None
    stall: int | None = None
    udp_active: int | None = None
    udp_inactive: int | None = None
    quality_source: str | None = None
    rtcp: str | None = None
    disk_used_pct: float | None = None
    disk_mount: str | None = None
    rx_errors: float | None = None
    rx_drops: float | None = None
    open_fds: int | None = None
    threads: int | None = None
    ipc_sent_ps: float | None = None
    ipc_recv_ps: float | None = None
    ipc_latency_ms: float | None = None
    runqueue: float | None = None
    buffers_mb: float | None = None
    cached_mb: float | None = None
    udp_pps_in: float | None = None
    udp_pps_out: float | None = None
    nic_rx_mbps: float | None = None
    nic_tx_mbps: float | None = None
    proc_cpu_pct: float | None = None
    proc_mem_pct: float | None = None
    udp_sockets: int | None = None
    rtp_gb: float | None = None
    recorded_at: datetime | None = None


class VoiceMgExtrasRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    servers: list[VoiceMgExtraRead]


class VoiceMgHistoryPointRead(BaseModel):
    ts: datetime
    active_calls: float | None = None
    mos: float | None = None
    jitter_ms: float | None = None
    packet_loss_pct: float | None = None
    rtp_mbps: float | None = None
    rtp_mbps_in: float | None = None
    rtp_mbps_out: float | None = None
    rtp_mbps_exp: float | None = None
    cpu_pct: float | None = None
    mem_pct: float | None = None
    rx_errors: float | None = None
    rx_drops: float | None = None
    open_fds: float | None = None
    threads: float | None = None
    ipc_sent_ps: float | None = None
    ipc_recv_ps: float | None = None
    ipc_latency_ms: float | None = None
    runqueue: float | None = None
    buffers_mb: float | None = None
    cached_mb: float | None = None
    udp_pps_in: float | None = None
    udp_pps_out: float | None = None
    nic_rx_mbps: float | None = None
    nic_tx_mbps: float | None = None
    proc_cpu_pct: float | None = None
    proc_mem_pct: float | None = None
    udp_sockets: float | None = None
    rtp_gb: float | None = None
    disk_used_pct: float | None = None


class VoiceMgHistoryRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    range: str
    group: str
    since: datetime | None = None
    until: datetime | None = None
    bucket_seconds: int = 10
    host_count: int = 0
    point_count: int = 0
    points: list[VoiceMgHistoryPointRead]
    server_id: int | None = None
    host_name: str | None = None


class LegacyMetricPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    source_id: int
    server_id: int | None
    host_key: str | None
    metric_key: str
    metric_value_num: float | None
    metric_value_text: str | None
    recorded_at: datetime
    synced_at: datetime
