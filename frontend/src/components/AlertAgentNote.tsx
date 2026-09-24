import { useState } from 'react'
import type { AlertSuggestion, LiveAlert } from '../types'

const STORE_KEY = 'worktual_alert_notify'

type Channel = 'gmail' | 'outlook'

type Props = {
  alert: LiveAlert
  suggestion: AlertSuggestion
}

function readSynced(): Record<string, Channel[]> {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, Channel[]>
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function remember(sourceId: number, channel: Channel) {
  const all = readSynced()
  const key = String(sourceId)
  const current = all[key] ?? []
  if (!current.includes(channel)) all[key] = [...current, channel]
  localStorage.setItem(STORE_KEY, JSON.stringify(all))
}

function mailBody(alert: LiveAlert, suggestion: AlertSuggestion): { subject: string; body: string } {
  const host = alert.inventory_server_name || alert.portal_server_name || alert.hostname || 'Host'
  const subject = `[${suggestion.team}] ${host}: ${alert.title}`
  const body = [
    `${host} · ${alert.ip_address || '—'}`,
    alert.title,
    '',
    `Reason: ${suggestion.why}`,
    `What to do: ${suggestion.solution}`,
    `Team to work: ${suggestion.team}`,
    `Estimated time: ${suggestion.time_estimate}`,
    '',
    'From Worktual Observability. A restart still needs Approve and Confirm run.',
  ].join('\n')
  return { subject, body }
}

function composeUrl(channel: Channel, subject: string, body: string): string {
  const su = encodeURIComponent(subject)
  const text = encodeURIComponent(body)
  if (channel === 'gmail') {
    return `https://mail.google.com/mail/?view=cm&fs=1&su=${su}&body=${text}`
  }
  return `https://outlook.office.com/mail/deeplink/compose?subject=${su}&body=${text}`
}

function GmailMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden>
      <path fill="#4caf50" d="M45 16.2 35 23.7V40h7c1.7 0 3-1.3 3-3V16.2z" />
      <path fill="#1e88e5" d="M3 16.2 13 23.7V40H6c-1.7 0-3-1.3-3-3V16.2z" />
      <path fill="#e53935" d="m35 11.2-11 8.25-11-8.25L12 17l1 6.7L24 32l11-8.3 1-6.7z" />
      <path fill="#c62828" d="M3 12.3V16.2l10 7.5V11.2L9.9 8.9A4.3 4.3 0 0 0 7.3 8C4.9 8 3 9.9 3 12.3z" />
      <path fill="#fbc02d" d="M45 12.3V16.2l-10 7.5V11.2l3.1-2.3c.8-.6 1.7-.9 2.6-.9 2.4 0 4.3 1.9 4.3 4.3z" />
    </svg>
  )
}

function OutlookMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden>
      <path fill="#1976d2" d="M28 13h14.5c.8 0 1.5.7 1.5 1.5v19c0 .8-.7 1.5-1.5 1.5H28V13z" />
      <path fill="#fff" d="M30.5 18h10v1.6h-10zm0 4h8v1.6h-8zm0 4h10v1.6h-10z" />
      <rect x="4" y="16" width="16" height="16" rx="2" fill="#03a9f4" />
      <ellipse cx="12" cy="24" rx="4.2" ry="4.6" fill="#fff" />
    </svg>
  )
}

export function AlertNotify({ alert, suggestion }: Props) {
  const [synced, setSynced] = useState<Channel[]>(() => readSynced()[String(alert.source_id)] ?? [])

  function notify(channel: Channel) {
    const { subject, body } = mailBody(alert, suggestion)
    const opened = window.open(composeUrl(channel, subject, body), '_blank', 'noopener,noreferrer')
    if (opened) opened.opener = null
    remember(alert.source_id, channel)
    setSynced((prev) => (prev.includes(channel) ? prev : [...prev, channel]))
  }

  return (
    <div className="alert-notify">
      <span className="alert-notify-label">Notify team</span>
      <button
        type="button"
        className={`alert-notify-btn${synced.includes('gmail') ? ' synced' : ''}`}
        aria-label={`Notify ${suggestion.team} in Gmail`}
        title={synced.includes('gmail') ? 'Opened in Gmail' : 'Open in Gmail'}
        onClick={() => notify('gmail')}
      >
        <GmailMark />
      </button>
      <button
        type="button"
        className={`alert-notify-btn${synced.includes('outlook') ? ' synced' : ''}`}
        aria-label={`Notify ${suggestion.team} in Outlook`}
        title={synced.includes('outlook') ? 'Opened in Outlook' : 'Open in Outlook'}
        onClick={() => notify('outlook')}
      >
        <OutlookMark />
      </button>
    </div>
  )
}

export function AlertAgentNote({ suggestion }: { suggestion: AlertSuggestion }) {
  return (
    <div className="alert-agent">
      <p className="alert-agent-live">
        <span className="live-dot" aria-hidden />
        Agent
      </p>
      <div className="alert-agent-rows">
        <p>
          <span>Reason</span>
          {suggestion.why}
        </p>
        <p>
          <span>What to do</span>
          {suggestion.solution}
        </p>
        <p>
          <span>Team to work</span>
          {suggestion.team}
        </p>
        <p>
          <span>Estimated time</span>
          {suggestion.time_estimate}
        </p>
      </div>
    </div>
  )
}
