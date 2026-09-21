import { useMemo, useState } from 'react'
import type {
  InventoryBaremetal,
  InventoryCatalog,
  InventoryCluster,
  InventoryDashboard,
  InventoryHost,
  InventoryPortal as InventoryPortalData,
  InventoryVm,
} from '../api'

function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

function fmtGb(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  if (value >= 1024) return `${(value / 1024).toFixed(1)} TB`
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} GB`
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`
}

function barClass(pct: number | null | undefined): string {
  if (pct == null) return 'bv-bar-fill'
  if (pct >= 90) return 'bv-bar-fill crit'
  if (pct >= 80) return 'bv-bar-fill warn'
  return 'bv-bar-fill'
}

function UtilBar({
  label,
  used,
  total,
  pct,
  unit = '',
}: {
  label: string
  used: number | null
  total: number | null
  pct: number | null
  unit?: string
}) {
  return (
    <article className="bv-card">
      <div className="bv-card-top">
        <strong>{label}</strong>
        <span className="bv-mono">{fmtPct(pct)}</span>
      </div>
      <p className="muted bv-sub">
        {used == null ? '—' : `${fmtNum(used, used >= 10 ? 0 : 1)}${unit}`}
        {' / '}
        {total == null ? '—' : `${fmtNum(total, total >= 10 ? 0 : 1)}${unit}`}
      </p>
      <div className="bv-bar" aria-hidden>
        <div className={barClass(pct)} style={{ width: `${Math.min(100, pct ?? 0)}%` }} />
      </div>
    </article>
  )
}

function StatusPill({ status }: { status: string | null }) {
  const value = (status || 'unknown').toLowerCase()
  const kind = ['running', 'online', 'active', 'up', 'ok', 'healthy'].includes(value)
    ? 'ok'
    : ['stopped', 'offline', 'down', 'failed'].includes(value)
      ? 'fail'
      : 'unknown'
  return <span className={`bv-pill bv-pill--${kind}`}>{value.toUpperCase()}</span>
}

function unique(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((v): v is string => Boolean(v)))).sort()
}

export type InventoryLiveTab =
  | 'dashboard'
  | 'baremetal'
  | 'proxmox'
  | 'realtime-hosts'
  | 'vms'
  | 'realtime-vms'
  | 'network'

type Props = {
  data: InventoryPortalData | null
  catalog?: InventoryCatalog | null
  loading: boolean
  onRefresh: () => void
  tab: InventoryLiveTab
}

export function InventoryPortal({ data, catalog, loading, onRefresh, tab }: Props) {
  if (!data && loading) {
    return <p className="muted">Loading inventory…</p>
  }
  if (!data) {
    return <p className="muted">Inventory not loaded.</p>
  }
  if (!data.ok) {
    return (
      <section className="bv-portal">
        <p className="banner error">{data.reason || 'Could not read server_inventory'}</p>
        <button type="button" className="btn ghost" onClick={onRefresh}>
          Retry
        </button>
      </section>
    )
  }

  if (tab === 'dashboard') {
    return <Dashboard data={data} catalog={catalog} loading={loading} onRefresh={onRefresh} />
  }
  if (tab === 'baremetal') {
    return <BaremetalTable rows={data.baremetal} loading={loading} onRefresh={onRefresh} />
  }
  if (tab === 'proxmox') {
    return (
      <ProxmoxView
        clusters={data.clusters}
        hosts={data.hosts}
        loading={loading}
        onRefresh={onRefresh}
      />
    )
  }
  if (tab === 'realtime-hosts') {
    return <RealtimeHosts hosts={data.hosts} loading={loading} onRefresh={onRefresh} />
  }
  if (tab === 'realtime-vms') {
    return <RealtimeVms rows={data.vms} loading={loading} onRefresh={onRefresh} />
  }
  if (tab === 'network') {
    return <NetworkView data={data} loading={loading} onRefresh={onRefresh} />
  }
  return <VmTable rows={data.vms} loading={loading} onRefresh={onRefresh} />
}

function Dashboard({
  data,
  catalog,
  loading,
  onRefresh,
}: {
  data: InventoryPortalData
  catalog?: InventoryCatalog | null
  loading: boolean
  onRefresh: () => void
}) {
  const dash: InventoryDashboard = data.dashboard
  const teams = dash.teams ?? []
  const money = catalog?.did_monthly_cost
  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Inventory dashboard</h2>
          <p className="muted">
            Live SELECT from MariaDB <code>{data.database || 'server_inventory'}</code> — no
            passwords. Totals are baremetal + Proxmox nodes + VMs.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Total servers</span>
          <span className="stat-value">{dash.total_servers}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Online</span>
          <span className="stat-value accent">{dash.online_servers}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total VMs</span>
          <span className="stat-value">{dash.total_vms}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active VMs</span>
          <span className="stat-value accent">{dash.active_vms}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Baremetal</span>
          <span className="stat-value">{dash.baremetal_count}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Proxmox nodes</span>
          <span className="stat-value">{dash.host_count}</span>
        </div>
      </div>
      <h3 className="bv-group-title">Resource utilization</h3>
      <div className="bv-card-grid">
        <UtilBar
          label="CPU pool"
          used={dash.cpu_used}
          total={dash.cpu_total}
          pct={dash.cpu_pct}
          unit=" cores"
        />
        <UtilBar
          label="RAM pool"
          used={dash.ram_used_gb}
          total={dash.ram_total_gb}
          pct={dash.ram_pct}
          unit=" GB"
        />
        <UtilBar
          label="Storage pool"
          used={dash.storage_used_gb}
          total={dash.storage_total_gb}
          pct={dash.storage_pct}
          unit=" GB"
        />
      </div>
      {teams.length ? (
        <>
          <h3 className="bv-group-title">Team VM usage</h3>
          <div className="bv-card-grid">
            {teams.map((team) => (
              <UtilBar
                key={team.name}
                label={team.name}
                used={team.count}
                total={dash.total_vms}
                pct={team.pct}
                unit=" VMs"
              />
            ))}
          </div>
        </>
      ) : null}
      {catalog?.ok ? (
        <>
          <h3 className="bv-group-title">DID / Domains / SSL</h3>
          <div className="stat-row backupvault-stat-row">
            <div className="stat-card">
              <span className="stat-label">DIDs</span>
              <span className="stat-value">{catalog.did_total}</span>
              <span className="muted bv-sub">{catalog.did_allocated} allocated</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Available / reserved</span>
              <span className="stat-value">
                {catalog.did_available ?? 0}/{catalog.did_reserved ?? 0}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Monthly DID cost</span>
              <span className="stat-value">{money == null ? '—' : money.toLocaleString()}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Domains</span>
              <span className="stat-value">{catalog.domain_total}</span>
              <span className="muted bv-sub">{catalog.domain_active ?? 0} active</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">SSL certs</span>
              <span className="stat-value">{catalog.ssl_total}</span>
              <span className="muted bv-sub">
                {catalog.ssl_active ?? 0} active · {catalog.ssl_expiring} expiring
              </span>
            </div>
          </div>
        </>
      ) : null}
      <h3 className="bv-group-title">Clusters ({data.clusters.length})</h3>
      <div className="bv-card-grid bv-storage-grid">
        {data.clusters.map((cluster) => (
          <ClusterCard key={cluster.id} cluster={cluster} />
        ))}
      </div>
    </section>
  )
}

function ClusterCard({ cluster }: { cluster: InventoryCluster }) {
  return (
    <article className="bv-card bv-storage-card">
      <div className="bv-card-top">
        <strong>{cluster.cluster_label || cluster.cluster_name}</strong>
        <span className="bv-pill bv-pill--unknown">{cluster.total_nodes} nodes</span>
      </div>
      <p className="muted bv-sub">
        {cluster.cluster_name}
        {cluster.total_vms ? ` · ${cluster.total_vms} VMs` : ''}
      </p>
      <p className="bv-card-meta">
        CPU {fmtNum(cluster.used_cpu, 0)}/{fmtNum(cluster.total_cpu, 0)} · RAM{' '}
        {fmtGb(cluster.used_ram_gb)}/{fmtGb(cluster.total_ram_gb)} · Disk{' '}
        {fmtGb(cluster.used_storage_gb)}/{fmtGb(cluster.total_storage_gb)}
      </p>
      <div className="bv-bar" aria-hidden>
        <div
          className={barClass(cluster.cpu_pct)}
          style={{ width: `${Math.min(100, cluster.cpu_pct ?? 0)}%` }}
        />
      </div>
    </article>
  )
}

function BaremetalTable({
  rows,
  loading,
  onRefresh,
}: {
  rows: InventoryBaremetal[]
  loading: boolean
  onRefresh: () => void
}) {
  const [cluster, setCluster] = useState('all')
  const [query, setQuery] = useState('')
  const clusters = useMemo(() => unique(rows.map((r) => r.cluster)), [rows])
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((row) => {
      if (cluster !== 'all' && row.cluster !== cluster) return false
      if (!q) return true
      return [
        row.hostname,
        row.order_id,
        row.server_id,
        row.host_public_ip,
        row.engineer,
        row.os,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    })
  }, [rows, cluster, query])

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Baremetal servers</h2>
          <p className="muted">{rows.length} physical hosts from the portal — credentials omitted.</p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="bv-filters">
        <label>
          Cluster
          <select value={cluster} onChange={(e) => setCluster(e.target.value)}>
            <option value="all">All</option>
            {clusters.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Search
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="hostname, order, IP…"
          />
        </label>
      </div>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>Order</th>
              <th>Server ID</th>
              <th>Hostname</th>
              <th>Public IP</th>
              <th>iLO</th>
              <th>Cluster</th>
              <th>OS</th>
              <th>Engineer</th>
              <th>CPU / RAM</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td className="bv-mono">{row.order_id ?? '—'}</td>
                <td className="bv-mono">{row.server_id ?? '—'}</td>
                <td>
                  {row.hostname ?? '—'}
                  {row.status ? (
                    <>
                      <br />
                      <StatusPill status={row.status} />
                    </>
                  ) : null}
                </td>
                <td className="bv-mono">{row.host_public_ip ?? '—'}</td>
                <td className="bv-mono">{row.ilo_private_ip ?? '—'}</td>
                <td>
                  {row.cluster ?? '—'}
                  {row.cluster_group ? <div className="muted bv-sub">{row.cluster_group}</div> : null}
                </td>
                <td>{row.os ?? '—'}</td>
                <td>{row.engineer ?? '—'}</td>
                <td>
                  {row.cpu ?? '—'}
                  {row.ram ? ` · ${row.ram}` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!filtered.length ? <p className="muted">No baremetal rows match the filter.</p> : null}
    </section>
  )
}

function ProxmoxView({
  clusters,
  hosts,
  loading,
  onRefresh,
}: {
  clusters: InventoryCluster[]
  hosts: InventoryHost[]
  loading: boolean
  onRefresh: () => void
}) {
  const [cluster, setCluster] = useState('all')
  const names = useMemo(() => unique(hosts.map((h) => h.cluster_name)), [hosts])
  const filtered = useMemo(
    () => hosts.filter((h) => cluster === 'all' || h.cluster_name === cluster),
    [hosts, cluster],
  )

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Proxmox hosts</h2>
          <p className="muted">
            {clusters.length} clusters · {hosts.length} nodes. Live node stats joined when present.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="bv-card-grid bv-storage-grid">
        {clusters.map((item) => (
          <ClusterCard key={item.id} cluster={item} />
        ))}
      </div>
      <div className="bv-filters">
        <label>
          Cluster
          <select value={cluster} onChange={(e) => setCluster(e.target.value)}>
            <option value="all">All</option>
            {names.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>Node</th>
              <th>Cluster</th>
              <th>IPs</th>
              <th>CPU</th>
              <th>RAM</th>
              <th>Storage</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((host) => (
              <tr key={host.id}>
                <td>{host.node_name}</td>
                <td>{host.cluster_label || host.cluster_name || '—'}</td>
                <td className="bv-mono">
                  {host.host_public_ip ?? '—'}
                  {host.host_private_ip ? <div className="muted bv-sub">{host.host_private_ip}</div> : null}
                </td>
                <td className="bv-mono">
                  {fmtPct(host.cpu_pct)}
                  <div className="muted bv-sub">
                    {fmtNum(host.used_cpu, 0)}/{fmtNum(host.total_cpu, 0)}
                  </div>
                </td>
                <td className="bv-mono">
                  {fmtPct(host.ram_pct)}
                  <div className="muted bv-sub">
                    {fmtGb(host.used_ram_gb)} / {fmtGb(host.total_ram_gb)}
                  </div>
                </td>
                <td className="bv-mono">
                  {fmtPct(host.storage_pct)}
                  <div className="muted bv-sub">
                    {fmtGb(host.used_storage_gb)} / {fmtGb(host.total_storage_gb)}
                  </div>
                </td>
                <td>
                  <StatusPill status={host.status} />
                  {host.updated_at ? (
                    <div className="muted bv-sub">{new Date(host.updated_at).toLocaleString()}</div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function VmTable({
  rows,
  loading,
  onRefresh,
}: {
  rows: InventoryVm[]
  loading: boolean
  onRefresh: () => void
}) {
  const [cluster, setCluster] = useState('all')
  const [node, setNode] = useState('all')
  const [team, setTeam] = useState('all')
  const [status, setStatus] = useState('all')
  const [query, setQuery] = useState('')
  const clusters = useMemo(() => unique(rows.map((r) => r.cluster_name)), [rows])
  const nodes = useMemo(() => unique(rows.map((r) => r.node_name)), [rows])
  const teams = useMemo(() => unique(rows.map((r) => r.team)), [rows])
  const statuses = useMemo(() => unique(rows.map((r) => r.status)), [rows])
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((row) => {
      if (cluster !== 'all' && row.cluster_name !== cluster) return false
      if (node !== 'all' && row.node_name !== node) return false
      if (team !== 'all' && row.team !== team) return false
      if (status !== 'all' && row.status !== status) return false
      if (!q) return true
      return [
        row.vm_id,
        row.guest_hostname,
        row.guest_ip_private,
        row.guest_ip_public,
        row.services,
        row.node_name,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    })
  }, [rows, cluster, node, team, status, query])

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Virtual machines</h2>
          <p className="muted">
            {rows.length} VMs · {filtered.length} shown. Live stats joined from live_vm_statistics.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="bv-filters">
        <label>
          Cluster
          <select value={cluster} onChange={(e) => setCluster(e.target.value)}>
            <option value="all">All</option>
            {clusters.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Node
          <select value={node} onChange={(e) => setNode(e.target.value)}>
            <option value="all">All</option>
            {nodes.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Team
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="all">All</option>
            {teams.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All</option>
            {statuses.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Search
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="VM ID, IP, service…"
          />
        </label>
      </div>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>VM ID</th>
              <th>Node / cluster</th>
              <th>IPs</th>
              <th>Services</th>
              <th>Team</th>
              <th>vCPU / RAM</th>
              <th>Live</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td className="bv-mono">
                  {row.vm_id}
                  {row.guest_hostname ? <div className="muted bv-sub">{row.guest_hostname}</div> : null}
                </td>
                <td>
                  {row.node_name ?? '—'}
                  {row.cluster_name ? <div className="muted bv-sub">{row.cluster_name}</div> : null}
                </td>
                <td className="bv-mono">
                  {row.guest_ip_private ?? '—'}
                  {row.guest_ip_public ? <div className="muted bv-sub">{row.guest_ip_public}</div> : null}
                </td>
                <td className="inv-services" title={row.services ?? ''}>
                  {row.services ?? '—'}
                </td>
                <td>{row.team ?? '—'}</td>
                <td className="bv-mono">
                  {row.cpu ?? '—'} vCPU
                  {row.ram_gb != null ? ` · ${fmtGb(row.ram_gb)}` : ''}
                </td>
                <td className="bv-mono">
                  CPU {fmtPct(row.cpu_util_pct)}
                  <div className="muted bv-sub">
                    RAM {fmtGb(row.ram_used_gb)} / {fmtGb(row.ram_total_gb)}
                  </div>
                </td>
                <td>
                  <StatusPill status={row.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!filtered.length ? <p className="muted">No VMs match the filter.</p> : null}
    </section>
  )
}

function fmtUptime(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  const days = seconds / 86400
  return `${days.toFixed(1)} days`
}

function RealtimeHosts({
  hosts,
  loading,
  onRefresh,
}: {
  hosts: InventoryHost[]
  loading: boolean
  onRefresh: () => void
}) {
  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Realtime hosts</h2>
          <p className="muted">Live CPU / memory / storage / uptime from `live_node_statistics` — view only.</p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>Node</th>
              <th>Cluster</th>
              <th>Live CPU</th>
              <th>Memory</th>
              <th>Storage</th>
              <th>Uptime</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {hosts.map((host) => (
              <tr key={host.id}>
                <td>{host.node_name}</td>
                <td>{host.cluster_label || host.cluster_name || '—'}</td>
                <td>{fmtPct(host.cpu_pct)}</td>
                <td>
                  {fmtGb(host.used_ram_gb)} / {fmtGb(host.total_ram_gb)}
                </td>
                <td>
                  {fmtGb(host.used_storage_gb)} / {fmtGb(host.total_storage_gb)}
                </td>
                <td>{fmtUptime(host.uptime_seconds)}</td>
                <td>
                  <StatusPill status={host.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function RealtimeVms({
  rows,
  loading,
  onRefresh,
}: {
  rows: InventoryVm[]
  loading: boolean
  onRefresh: () => void
}) {
  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Realtime VMs</h2>
          <p className="muted">
            {rows.length} workloads · live CPU / memory / storage from `live_vm_statistics`.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>VM / name</th>
              <th>IPs</th>
              <th>Node</th>
              <th>Live CPU</th>
              <th>Memory</th>
              <th>Storage</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.guest_hostname || row.vm_id}</strong>
                  <div className="muted bv-sub">{row.vm_id}</div>
                </td>
                <td className="bv-mono">
                  {row.guest_ip_private ?? '—'}
                  {row.guest_ip_public ? <div className="muted bv-sub">{row.guest_ip_public}</div> : null}
                </td>
                <td>{row.node_name ?? '—'}</td>
                <td>{fmtPct(row.cpu_util_pct)}</td>
                <td>
                  {fmtGb(row.ram_used_gb)} / {fmtGb(row.ram_total_gb ?? row.ram_gb)}
                </td>
                <td>
                  {fmtGb(row.storage_used_gb)} / {fmtGb(row.disk_gb)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function NetworkView({
  data,
  loading,
  onRefresh,
}: {
  data: InventoryPortalData
  loading: boolean
  onRefresh: () => void
}) {
  const net = data.network
  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Network statistics</h2>
          <p className="muted">
            Peak RX/TX from live VM telemetry{net?.source ? ` · ${net.source}` : ''} — no waveform if `.222` has no history rows.
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Peak inbound (RX)</span>
          <span className="stat-value">{net?.peak_rx_mbps == null ? '—' : `${net.peak_rx_mbps.toFixed(2)} Mbps`}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Peak outbound (TX)</span>
          <span className="stat-value">{net?.peak_tx_mbps == null ? '—' : `${net.peak_tx_mbps.toFixed(2)} Mbps`}</span>
        </div>
      </div>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>VM</th>
              <th>RX Mbps</th>
              <th>TX Mbps</th>
            </tr>
          </thead>
          <tbody>
            {(net?.points ?? []).map((point, index) => (
              <tr key={`${point.name}-${index}`}>
                <td>{point.name || '—'}</td>
                <td>{point.rx_mbps == null ? '—' : point.rx_mbps.toFixed(3)}</td>
                <td>{point.tx_mbps == null ? '—' : point.tx_mbps.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!net?.points.length ? <p className="muted">No stream data for this window on MariaDB.</p> : null}
    </section>
  )
}
