import type { ReactNode } from 'react'
import { SERVER_DOMAINS, type DomainId, countByDomain, serversInDomain } from '../serverDomains'
import type { Server } from '../types'

type Props = {
  servers: Server[]
  domainFilter: DomainId
  onDomainFilterChange: (id: DomainId) => void
  renderCard: (server: Server) => ReactNode
}

export function ServersByDomain({ servers, domainFilter, onDomainFilterChange, renderCard }: Props) {
  const counts = countByDomain(servers)

  return (
    <>
      <div className="domain-tabs" role="tablist" aria-label="Server domains">
        <button
          type="button"
          role="tab"
          className={`domain-tab ${domainFilter === 'all' ? 'active' : ''}`}
          aria-selected={domainFilter === 'all'}
          onClick={() => onDomainFilterChange('all')}
        >
          All
          <span className="domain-tab-count">{counts.all ?? servers.length}</span>
        </button>
        {SERVER_DOMAINS.map((d) => {
          const n = counts[d.id] ?? 0
          if (n === 0) return null
          return (
            <button
              key={d.id}
              type="button"
              role="tab"
              className={`domain-tab ${domainFilter === d.id ? 'active' : ''}`}
              aria-selected={domainFilter === d.id}
              onClick={() => onDomainFilterChange(d.id)}
            >
              {d.label}
              <span className="domain-tab-count">{n}</span>
            </button>
          )
        })}
      </div>

      {domainFilter === 'all' ? (
        <div className="domain-sections">
          {SERVER_DOMAINS.map((d) => {
            const list = serversInDomain(servers, d.id)
            if (list.length === 0) return null
            return (
              <section key={d.id} className={`domain-section domain-section--${d.id}`}>
                <header className="domain-section-head">
                  <h2>{d.label}</h2>
                  <p className="muted">{d.description}</p>
                  <span className="domain-section-count">{list.length} hosts</span>
                </header>
                <div className="server-grid">{list.map((s) => renderCard(s))}</div>
              </section>
            )
          })}
          {(counts.other ?? 0) > 0 ? (
            <section className="domain-section domain-section--other">
              <header className="domain-section-head">
                <h2>Other</h2>
                <p className="muted">Untagged or custom project hosts.</p>
                <span className="domain-section-count">{counts.other} hosts</span>
              </header>
              <div className="server-grid">{serversInDomain(servers, 'other').map((s) => renderCard(s))}</div>
            </section>
          ) : null}
        </div>
      ) : (
        <section className={`domain-section domain-section--${domainFilter} domain-section--solo`}>
          {SERVER_DOMAINS.filter((d) => d.id === domainFilter).map((d) => (
            <header key={d.id} className="domain-section-head">
              <h2>{d.label}</h2>
              <p className="muted">{d.description}</p>
            </header>
          ))}
          {domainFilter === 'other' ? (
            <header className="domain-section-head">
              <h2>Other</h2>
              <p className="muted">Untagged or custom project hosts.</p>
            </header>
          ) : null}
          <div className="server-grid">
            {serversInDomain(servers, domainFilter).map((s) => renderCard(s))}
          </div>
        </section>
      )}
    </>
  )
}
