import type { InventoryCatalog as Catalog, InventoryDid, InventoryDomain, InventorySsl } from '../api'

function day(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(0, 10)
}

function StatusPill({ status }: { status: string | null }) {
  const value = (status || 'unknown').toLowerCase()
  const kind = ['active', 'allocated', 'valid', 'ok', 'healthy'].includes(value)
    ? 'ok'
    : ['expired', 'released', 'failed', 'revoked'].includes(value)
      ? 'fail'
      : 'unknown'
  return <span className={`bv-pill bv-pill--${kind}`}>{value}</span>
}

type Tab = 'did' | 'ssl' | 'domains'

type Props = {
  data: Catalog | null
  loading: boolean
  tab: Tab
  onRefresh: () => void
}

export function InventoryCatalog({ data, loading, tab, onRefresh }: Props) {
  if (!data && loading) return <p className="muted">Loading catalog…</p>
  if (!data) return <p className="muted">Catalog not loaded.</p>
  if (!data.ok) {
    return (
      <section className="bv-portal">
        <p className="banner error">{data.reason || 'Could not read DID / SSL / domains'}</p>
        <button type="button" className="btn ghost" onClick={onRefresh}>
          Retry
        </button>
      </section>
    )
  }

  return (
    <section className="bv-portal">
      <div className="panel-head">
        <p className="muted">
          Read-only from MariaDB <code>server_inventory</code> — same lists as servers.worktual.tech. No add /
          edit / upload.
        </p>
        <button type="button" className="btn ghost" disabled={loading} onClick={onRefresh}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      {tab === 'did' ? <DidView data={data} /> : null}
      {tab === 'ssl' ? <SslView rows={data.ssl} expiring={data.ssl_expiring} /> : null}
      {tab === 'domains' ? <DomainView rows={data.domains} /> : null}
    </section>
  )
}

function DidView({ data }: { data: Catalog }) {
  return (
    <>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">DID numbers</span>
          <span className="stat-value">{data.did_total}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Allocated / active</span>
          <span className="stat-value">{data.did_allocated}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Providers</span>
          <span className="stat-value">{data.providers.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Clients</span>
          <span className="stat-value">{data.clients.length}</span>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>DID</th>
              <th>Status</th>
              <th>Provider</th>
              <th>Client</th>
              <th>Use / app</th>
              <th>Type</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {data.dids.length ? (
              data.dids.map((row: InventoryDid) => (
                <tr key={row.id}>
                  <td>
                    {row.did_number}
                    <br />
                    <span className="muted">
                      {[row.country_code, row.area_code].filter(Boolean).join(' ')}
                    </span>
                  </td>
                  <td>
                    <StatusPill status={row.status} />
                  </td>
                  <td>{row.provider || '—'}</td>
                  <td>{row.client || '—'}</td>
                  <td>
                    {row.use_case || '—'}
                    {row.application ? <span className="muted"> · {row.application}</span> : null}
                  </td>
                  <td>{row.number_type || '—'}</td>
                  <td>{row.monthly_cost == null ? '—' : row.monthly_cost}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="muted">
                  No DID numbers in server_inventory.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

function SslView({ rows, expiring }: { rows: InventorySsl[]; expiring: number }) {
  return (
    <>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Certificates</span>
          <span className="stat-value">{rows.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Expiring ≤30 days</span>
          <span className="stat-value warn">{expiring}</span>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Hostname</th>
              <th>Issuer</th>
              <th>Valid</th>
              <th>Days left</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.hostname}
                    {row.domain ? (
                      <>
                        <br />
                        <span className="muted">{row.domain}</span>
                      </>
                    ) : null}
                  </td>
                  <td>{row.issuer || '—'}</td>
                  <td>
                    {day(row.valid_from)} → {day(row.valid_to)}
                  </td>
                  <td>{row.remaining_days ?? '—'}</td>
                  <td>
                    <StatusPill status={row.status} />
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="muted">
                  No SSL certificates in server_inventory.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

function DomainView({ rows }: { rows: InventoryDomain[] }) {
  return (
    <>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Domains</span>
          <span className="stat-value">{rows.length}</span>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Domain</th>
              <th>Registrar</th>
              <th>Renewal</th>
              <th>Team</th>
              <th>Status</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.domain_name}</td>
                  <td>{row.registrar || '—'}</td>
                  <td>{day(row.renewal_date)}</td>
                  <td>{row.team || '—'}</td>
                  <td>
                    <StatusPill status={row.status} />
                  </td>
                  <td>{row.notes || '—'}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="muted">
                  No domains in server_inventory.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
