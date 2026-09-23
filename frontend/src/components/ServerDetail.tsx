import { useState, type ReactNode } from 'react'
import type { AiInsightExtra, AiInsightHistoryRange } from '../api'
import type { Server } from '../types'
import { AiInsightsHistory } from './AiInsightsHistory'

const RANGES: Array<{ id: AiInsightHistoryRange; label: string }> = [
  { id: '30m', label: '30 min' },
  { id: '60m', label: '60 min' },
  { id: '2h', label: '2 hours' },
  { id: 'today', label: 'Today' },
]

type Props = {
  server: Server
  extra?: AiInsightExtra
  onBack: () => void
  children: ReactNode
}

export function ServerDetail({ server, extra, onBack, children }: Props) {
  const [range, setRange] = useState<AiInsightHistoryRange>('60m')

  return (
    <div className="server-detail">
      <header className="page-head servers-status server-detail-bar">
        <p className="fleet-status-line">
          {server.server_name} · {server.ip_address}:{server.ssh_port}
        </p>
        <button type="button" className="btn ghost" onClick={onBack}>
          Back
        </button>
      </header>
      {extra ? (
        <section className="panel">
          <div className="ai-history-toolbar">
            <div className="bv-tabs" role="tablist" aria-label="Host history range">
              {RANGES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`bv-tab ${range === item.id ? 'active' : ''}`}
                  onClick={() => setRange(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <AiInsightsHistory
            range={range}
            group={extra.group_id || 'all'}
            serverId={extra.id}
            hostName={extra.server_name}
          />
        </section>
      ) : null}
      {children}
    </div>
  )
}
