import { useState } from 'react'

const RESTART_LABELS: Record<string, string> = {
  docker: 'Restart Docker',
  postfix: 'Restart Postfix',
  nginx: 'Restart nginx',
  kong: 'Restart Kong',
  'grafana-server': 'Restart Grafana',
}

function restartLabel(name: string) {
  return RESTART_LABELS[name] ?? `Restart ${name}`
}

type Props = {
  restartServices: string[]
  disabled?: boolean
  onRecollect: () => void
  onSshVerify: () => void
  onRestart?: (service: string) => void
}

export function ApprovalRequestButtons({
  restartServices,
  disabled = false,
  onRecollect,
  onSshVerify,
  onRestart,
}: Props) {
  const [picked, setPicked] = useState(restartServices[0] || '')
  const service = restartServices.includes(picked) ? picked : restartServices[0] || ''
  return (
    <div className="approval-request-row">
      <button type="button" className="btn ghost" disabled={disabled} onClick={onRecollect}>
        Request recollect
      </button>
      <button type="button" className="btn ghost" disabled={disabled} onClick={onSshVerify}>
        Request SSH verify
      </button>
      {restartServices.length > 1 && onRestart ? (
        <select
          className="approval-service-select"
          value={service}
          onChange={(e) => setPicked(e.target.value)}
          disabled={disabled}
          aria-label="Restart service"
        >
          {restartServices.map((name) => (
            <option key={name} value={name}>
              {restartLabel(name)}
            </option>
          ))}
        </select>
      ) : null}
      {restartServices.length > 0 && onRestart ? (
        <button
          type="button"
          className="btn ghost"
          disabled={disabled || !service}
          onClick={() => onRestart(service)}
        >
          {restartLabel(service)}
        </button>
      ) : null}
    </div>
  )
}
