import { useState } from 'react'
import { actionTitle, alertTitle, statusTitle } from '../agentLabels'
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
        <div>
          <p className="approval-card-kicker">{actionTitle(approval.action_key)}</p>
          <strong>{host}</strong>
        </div>
        <span className={`badge ${approval.status}`}>{statusTitle(approval.status)}</span>
      </header>
      <dl className="approval-meta">
        <div>
          <dt>Problem</dt>
          <dd>{approval.alert_reason || approval.request_notes || alertTitle(approval.alert_type, approval.action_key)}</dd>
        </div>
      </dl>
      <p className="approval-card-kicker">Command</p>
      <pre className="readonly-sample approval-command">
        {approval.proposed_command || actionTitle(approval.action_key)}
      </pre>
      {approval.impact ? (
        <>
          <p className="approval-card-kicker">Impact</p>
          <p className="approval-impact">{approval.impact}</p>
        </>
      ) : null}

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
              <p className="approval-confirm-copy">
                Confirm run on <strong>{approval.server_name}</strong>. Nothing has run yet.
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
        <p className="muted">{prettyResult(approval.execution_result)}</p>
      ) : null}
    </article>
  )
}

function prettyResult(raw: string): string {
  try {
    const parsed = JSON.parse(raw) as { message?: string }
    if (parsed.message) return parsed.message
  } catch {
    /* keep raw */
  }
  return raw
}
