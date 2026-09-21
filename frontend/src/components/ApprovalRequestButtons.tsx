import { useState } from 'react'

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
  const [service, setService] = useState(restartServices[0] || '')
  return (
    <div className="approval-request-row">
      <button type="button" className="btn ghost" disabled={disabled} onClick={onRecollect}>
        Request recollect
      </button>
      <button type="button" className="btn ghost" disabled={disabled} onClick={onSshVerify}>
        Request SSH verify
      </button>
      {restartServices.length > 0 && onRestart ? (
        <>
          <select
            className="approval-service-select"
            value={service}
            onChange={(e) => setService(e.target.value)}
            disabled={disabled}
            aria-label="Restart service"
          >
            {restartServices.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn ghost"
            disabled={disabled || !service}
            onClick={() => onRestart(service)}
          >
            Request restart
          </button>
        </>
      ) : null}
    </div>
  )
}
