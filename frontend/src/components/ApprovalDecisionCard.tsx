import { useState } from 'react'
import type { Approval } from '../types'

type Props = {
  approval: Approval
  onApprove: (id: number) => Promise<void>
  onReject: (id: number) => Promise<void>
}

export function ApprovalDecisionCard({ approval, onApprove, onReject }: Props) {
  const [step, setStep] = useState<'idle' | 'confirm'>('idle')
  const [busy, setBusy] = useState(false)
  const host = approval.host_label || `${approval.server_name} (${approval.ip_address})`

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    try {
      await fn()
    } finally {
      setBusy(false)
      setStep('idle')
    }
  }

  return (
    <article className="approval-card">
      <header className="approval-card-head">
        <strong>{host}</strong>
        <span className={`badge ${approval.status}`}>{approval.status}</span>
      </header>
      <p>
        <span className="metric-label">Alert</span> {approval.alert_type || approval.action_key}
      </p>
      <p>{approval.alert_reason || approval.request_notes || '—'}</p>
      <p>
        <span className="metric-label">Can the agent run this?</span>
      </p>
      <pre className="readonly-sample">
        {approval.proposed_command || approval.action_key}
        {approval.action_key === 'systemctl_restart' && approval.action_params
          ? `\n${approval.action_params}`
          : ''}
      </pre>
      {approval.impact ? <p className="muted">{approval.impact}</p> : null}

      {approval.status === 'pending' ? (
        <div className="approval-request-row">
          {step === 'idle' ? (
            <>
              <button type="button" className="btn primary" disabled={busy} onClick={() => setStep('confirm')}>
                Approve
              </button>
              <button
                type="button"
                className="btn ghost"
                disabled={busy}
                onClick={() => void run(() => onReject(approval.id))}
              >
                Reject
              </button>
            </>
          ) : (
            <>
              <p className="muted">
                Confirm run on <strong>{approval.server_name}</strong>? Second click required. Reject
                cancels.
              </p>
              <button
                type="button"
                className="btn primary"
                disabled={busy}
                onClick={() => void run(() => onApprove(approval.id))}
              >
                Confirm run
              </button>
              <button type="button" className="btn ghost" disabled={busy} onClick={() => setStep('idle')}>
                Cancel
              </button>
            </>
          )}
        </div>
      ) : approval.execution_result ? (
        <p className="muted">{approval.execution_result}</p>
      ) : null}
    </article>
  )
}
