import { useState } from 'react'
import { actionTitle, alertTitle, statusTitle } from '../agentLabels'
import { formatWhen } from '../formatWhen'
import type { Approval } from '../types'

type Props = {
  approval: Approval
  onApprove: (id: number) => Promise<void>
  onReject: (id: number) => Promise<void>
}

export function ApprovalDecisionCard({ approval, onApprove, onReject }: Props) {
  const [step, setStep] = useState<'idle' | 'confirm'>('idle')
  const [busy, setBusy] = useState(false)
  const host = `${approval.server_name} · ${approval.ip_address}`
  const when = formatWhen(approval.created_at)
  const reason = displayReason(approval)
  const command = (approval.proposed_command || '').trim()
  const shell = isShellCommand(command)

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
          <p className="approval-card-title">{actionTitle(approval.action_key)}</p>
          <p className="approval-card-host">
            {host}
            {when ? ` · ${when}` : ''}
          </p>
        </div>
        <span className={`badge ${approval.status}`}>{statusTitle(approval.status)}</span>
      </header>
      {reason ? <p className="approval-meta">{reason}</p> : null}
      {command ? (
        shell ? (
          <p className="approval-command">{command}</p>
        ) : (
          <p className="approval-problem">{command}</p>
        )
      ) : null}
      {approval.impact ? <p className="approval-impact">{approval.impact}</p> : null}

      {approval.status === 'pending' ? (
        <div className="approval-card-foot">
          {step === 'confirm' ? (
            <p className="approval-confirm-copy">
              Confirm run on {approval.server_name}. Nothing has run yet.
            </p>
          ) : (
            <span />
          )}
          <div className="approval-actions">
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
        </div>
      ) : approval.execution_result ? (
        <p className="approval-impact">{prettyResult(approval.execution_result)}</p>
      ) : null}
    </article>
  )
}

function isShellCommand(command: string): boolean {
  return /^(sudo\s|systemctl\s)/.test(command)
}

function displayReason(approval: Approval): string | null {
  const reason = (approval.alert_reason || '').trim()
  const notes = (approval.request_notes || '').trim()
  const boilerplate = `${approval.action_key} after operator review`
  if (reason && reason.toLowerCase() !== boilerplate.toLowerCase()) {
    return tidyMetrics(reason)
  }
  if (notes && notes.toLowerCase() !== boilerplate.toLowerCase() && !notes.toLowerCase().endsWith(' after operator review')) {
    return tidyMetrics(notes)
  }
  if (!reason && !notes) {
    const fallback = alertTitle(approval.alert_type, approval.action_key)
    return fallback === 'Requested by you' ? null : fallback
  }
  return null
}

function tidyMetrics(text: string): string {
  return text.replace(/(\d+\.\d{2,})/g, (value) => {
    const num = Number(value)
    if (Number.isNaN(num)) return value
    return String(Math.round(num * 10) / 10)
  })
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
