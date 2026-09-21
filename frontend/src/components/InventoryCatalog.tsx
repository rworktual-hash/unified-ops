import { useState } from 'react'
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
type DidSub = 'numbers' | 'allocations' | 'clients' | 'providers'

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
      {tab === 'ssl' ? (
        <SslView
          rows={data.ssl}
          active={data.ssl_active ?? 0}
          expiring={data.ssl_expiring}
          expired={data.ssl_expired ?? 0}
        />
      ) : null}
      {tab === 'domains' ? <DomainView data={data} /> : null}
    </section>
  )
}

function DidView({ data }: { data: Catalog }) {
  const [sub, setSub] = useState<DidSub>('numbers')
  return (
    <>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">DID numbers</span>
          <span className="stat-value">{data.did_total}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Available</span>
          <span className="stat-value">{data.did_available ?? 0}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Allocated</span>
          <span className="stat-value">{data.did_allocated}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Reserved</span>
          <span className="stat-value">{data.did_reserved ?? 0}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Clients</span>
          <span className="stat-value">{data.clients.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Monthly cost</span>
          <span className="stat-value">
            {data.did_monthly_cost == null ? '—' : data.did_monthly_cost.toLocaleString()}
          </span>
        </div>
      </div>
      <div className="bv-tabs" aria-label="DID sections">
        {(
          [
            ['numbers', 'Numbers'],
            ['allocations', `Allocations${data.allocations?.length ? ` (${data.allocations.length})` : ''}`],
            ['clients', `Clients (${data.clients.length})`],
            ['providers', `Providers (${data.providers.length})`],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={sub === id ? 'bv-tab active' : 'bv-tab'}
            onClick={() => setSub(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {sub === 'numbers' ? <DidNumbers rows={data.dids} /> : null}
      {sub === 'allocations' ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>DID</th>
                <th>Client</th>
                <th>Status</th>
                <th>Use</th>
                <th>Allocated</th>
              </tr>
            </thead>
            <tbody>
              {(data.allocations ?? []).map((row) => (
                <tr key={row.id}>
                  <td>{row.did_number || '—'}</td>
                  <td>{row.client || '—'}</td>
                  <td>
                    <StatusPill status={row.status ?? null} />
                  </td>
                  <td>
                    {row.use_case || '—'}
                    {row.application ? <span className="muted"> · {row.application}</span> : null}
                  </td>
                  <td>{day(row.allocated_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.allocations?.length ? <p className="muted">No allocation rows.</p> : null}
        </div>
      ) : null}
      {sub === 'clients' ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Client</th>
                <th>Contact</th>
                <th>Email</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.clients.map((row) => (
                <tr key={row.id}>
                  <td>{row.company_name || '—'}</td>
                  <td>{row.contact_name || '—'}</td>
                  <td>{row.contact_email || '—'}</td>
                  <td>
                    <StatusPill status={row.status ?? null} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {sub === 'providers' ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Contact</th>
                <th>Email</th>
                <th>Phone</th>
              </tr>
            </thead>
            <tbody>
              {data.providers.map((row) => (
                <tr key={row.id}>
                  <td>{row.provider_name || '—'}</td>
                  <td>{row.contact_person || '—'}</td>
                  <td>{row.support_email || '—'}</td>
                  <td>{row.support_phone || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  )
}

function DidNumbers({ rows }: { rows: InventoryDid[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>DID</th>
            <th>Provider</th>
            <th>Type</th>
            <th>Status</th>
            <th>Client</th>
            <th>Contact</th>
            <th>Email</th>
            <th>KYC</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row: InventoryDid) => (
              <tr key={row.id}>
                <td>
                  {row.did_number}
                  <br />
                  <span className="muted">{[row.country_code, row.area_code].filter(Boolean).join(' ')}</span>
                </td>
                <td>{row.provider || '—'}</td>
                <td>{row.number_type || '—'}</td>
                <td>
                  <StatusPill status={row.status} />
                </td>
                <td>{row.client || '—'}</td>
                <td>{row.contact || '—'}</td>
                <td>{row.email || '—'}</td>
                <td>{row.kyc_name || '—'}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={8} className="muted">
                No DID numbers in server_inventory.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function SslView({
  rows,
  active,
  expiring,
  expired,
}: {
  rows: InventorySsl[]
  active: number
  expiring: number
  expired: number
}) {
  return (
    <>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Certificates</span>
          <span className="stat-value">{rows.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active</span>
          <span className="stat-value accent">{active}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Expiring ≤30 days</span>
          <span className="stat-value warn">{expiring}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Expired</span>
          <span className="stat-value warn">{expired}</span>
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

function DomainView({ data }: { data: Catalog }) {
  const rows: InventoryDomain[] = data.domains
  return (
    <>
      <div className="stat-row backupvault-stat-row">
        <div className="stat-card">
          <span className="stat-label">Domains</span>
          <span className="stat-value">{data.domain_total}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active</span>
          <span className="stat-value accent">{data.domain_active ?? 0}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Expiring</span>
          <span className="stat-value warn">{data.domain_expiring ?? 0}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Expired</span>
          <span className="stat-value warn">{data.domain_expired ?? 0}</span>
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
