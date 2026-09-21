import { useState } from 'react'
import { actionTitle } from '../agentLabels'
import type { AgentAction } from '../types'

type Props = {
  items: AgentAction[]
}

export function AgentLogList({ items }: Props) {
  return (
    <ul className="agent-log">
      {items.map((aa) => (
        <AgentLogItem key={aa.id} item={aa} />
      ))}
    </ul>
  )
}

function AgentLogItem({ item }: { item: AgentAction }) {
  const [open, setOpen] = useState(false)
  const when = item.created_at ? new Date(item.created_at).toLocaleString() : ''
  return (
    <li className="agent-log-item">
      <button type="button" className="agent-log-head" onClick={() => setOpen((v) => !v)}>
        <span className={`badge ${item.action_type === 'execute' ? 'executed' : 'pending'}`}>
          {actionTitle(item.action_type)}
        </span>
        <strong>{item.summary}</strong>
        <span className="muted">
          Server #{item.server_id}
          {when ? ` · ${when}` : ''}
        </span>
      </button>
      {open ? (
        <div className="agent-log-body">
          <pre className="diagnosis">{item.diagnosis}</pre>
        </div>
      ) : null}
    </li>
  )
}
