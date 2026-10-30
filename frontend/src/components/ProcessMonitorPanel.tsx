import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkProcessWatch,
  createProcessWatch,
  deleteProcessWatch,
  listProcessWatches,
  type ProcessWatch,
} from '../api'
import { formatWhen, parseWhen } from '../formatWhen'

type Props = {
  isAdmin: boolean
}

function mailLine(row: ProcessWatch): string {
  if (row.mail_sent === false) return row.mail_error || 'Mail was not sent'
  if (row.mail_sent && row.last_emailed_at) return `Mail sent ${formatWhen(row.last_emailed_at)}`
  return 'No mail yet'
}

function watchTitle(row: ProcessWatch): string {
  return row.label.trim() || row.process_name
}

function everyLabel(amount: number, unit: 'seconds' | 'minutes' | string): string {
  const name = unit === 'minutes' ? 'min' : 'sec'
  return `${amount} ${name}`
}

function intervalMs(row: ProcessWatch): number {
  return row.check_interval_unit === 'minutes' ? row.check_interval * 60_000 : row.check_interval * 1000
}

function remainingMs(row: ProcessWatch, now: number): number {
  const checked = parseWhen(row.last_checked_at)
  if (checked == null) return 0
  return Math.max(0, checked + intervalMs(row) - now)
}

function countdownText(ms: number): string {
  const total = Math.ceil(ms / 1000)
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  if (minutes > 0) return `${minutes}:${String(seconds).padStart(2, '0')}`
  return `${seconds}s`
}

export function ProcessAlertSection({
  watches,
  showResolved,
}: {
  watches: ProcessWatch[]
  showResolved: boolean
}) {
  const open = watches.filter((row) => row.status === 'down')
  const resolved = watches.filter((row) => row.status === 'up' && row.resolved_at)
  const shown = showResolved ? [...open, ...resolved] : open
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Process</h2>
      </div>
      {shown.length === 0 ? (
        <p className="muted">{showResolved ? 'No process alerts.' : 'No open process alerts.'}</p>
      ) : (
        <div className="alert-list">
          {shown.map((row) => (
            <article className="alert-item" key={row.id}>
              <span className={`badge ${row.status === 'down' ? 'critical' : 'ok'}`}>
                {row.status === 'down' ? 'down' : 'up'}
              </span>
              <div className="alert-copy">
                <div className="alert-title-line">
                  <strong>{watchTitle(row)}</strong>
                  <span className="muted">
                    {row.process_name} · {row.ip_address}
                  </span>
                </div>
                <p className="alert-title">
                  {row.status === 'down' ? 'Process is not running' : 'Process is running again'}
                </p>
                <p className="alert-message">
                  Down since {row.down_since ? formatWhen(row.down_since) : '—'} · {mailLine(row)}
                </p>
              </div>
              <time className="alert-when">{formatWhen(row.last_checked_at)}</time>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export function ProcessMonitorPanel({ isAdmin }: Props) {
  const [rows, setRows] = useState<ProcessWatch[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [checkingId, setCheckingId] = useState<number | null>(null)
  const [ip, setIp] = useState('')
  const [port, setPort] = useState('22')
  const [username, setUsername] = useState('root')
  const [password, setPassword] = useState('')
  const [label, setLabel] = useState('')
  const [processName, setProcessName] = useState('')
  const [recipients, setRecipients] = useState('')
  const [checkEvery, setCheckEvery] = useState('60')
  const [checkUnit, setCheckUnit] = useState<'seconds' | 'minutes'>('seconds')
  const [mailEvery, setMailEvery] = useState('5')
  const [now, setNow] = useState(() => Date.now())
  const inFlight = useRef<Set<number>>(new Set())
  const retryAt = useRef<Record<number, number>>({})

  const load = useCallback(async () => {
    setRows(await listProcessWatches())
  }, [])

  useEffect(() => {
    void load().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to load process watches')
    })
  }, [load])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void listProcessWatches()
        .then(setRows)
        .catch(() => undefined)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!isAdmin) return
    for (const row of rows) {
      if (inFlight.current.has(row.id)) continue
      if ((retryAt.current[row.id] ?? 0) > now) continue
      if (remainingMs(row, now) > 0) continue
      inFlight.current.add(row.id)
      setCheckingId(row.id)
      void checkProcessWatch(row.id)
        .then((updated) => {
          setRows((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
        })
        .catch((err: unknown) => {
          retryAt.current[row.id] = Date.now() + 5000
          setError(err instanceof Error ? err.message : 'Process check failed')
        })
        .finally(() => {
          inFlight.current.delete(row.id)
          setCheckingId((current) => (current === row.id ? null : current))
        })
    }
  }, [isAdmin, now, rows])

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Watches</h2>
            <p className="muted-block">
              Each watch checks itself when its timer reaches zero. The timer counts down on the card.
              Mail repeats on the mail interval while the process stays down.
            </p>
          </div>
        </div>
        {error ? <p className="banner error">{error}</p> : null}
        {isAdmin ? (
          <form
            className="process-create"
            onSubmit={async (event) => {
              event.preventDefault()
              setBusy(true)
              setError(null)
              try {
                const created = await createProcessWatch({
                  ip_address: ip.trim(),
                  ssh_port: Number(port),
                  ssh_username: username.trim() || 'root',
                  ssh_password: password,
                  label: label.trim(),
                  process_name: processName.trim(),
                  recipients: recipients.split(/[,;\s]+/).filter(Boolean),
                  check_interval: Number(checkEvery),
                  check_interval_unit: checkUnit,
                  mail_interval_minutes: Number(mailEvery),
                })
                setIp('')
                setLabel('')
                setPassword('')
                setProcessName('')
                setRecipients('')
                setRows((prev) => [created, ...prev.filter((row) => row.id !== created.id)])
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to add process watch')
              } finally {
                setBusy(false)
              }
            }}
          >
            <label className="field-label">
              Label
              <input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="STT TTS"
                required
              />
            </label>
            <label className="field-label">
              Server IP
              <input value={ip} onChange={(event) => setIp(event.target.value)} required />
            </label>
            <label className="field-label">
              SSH port
              <input
                value={port}
                onChange={(event) => setPort(event.target.value)}
                inputMode="numeric"
                required
              />
            </label>
            <label className="field-label">
              Username
              <input value={username} onChange={(event) => setUsername(event.target.value)} required />
            </label>
            <label className="field-label">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
            <label className="field-label">
              Process name
              <input
                value={processName}
                onChange={(event) => setProcessName(event.target.value)}
                placeholder="nginx"
                required
              />
            </label>
            <label className="field-label">
              Mail ids
              <input
                value={recipients}
                onChange={(event) => setRecipients(event.target.value)}
                placeholder="a@example.com, b@example.com"
                required
              />
            </label>
            <label className="field-label">
              Check every
              <input
                value={checkEvery}
                onChange={(event) => setCheckEvery(event.target.value)}
                inputMode="numeric"
                required
              />
            </label>
            <label className="field-label">
              Check unit
              <select value={checkUnit} onChange={(event) => setCheckUnit(event.target.value as 'seconds' | 'minutes')}>
                <option value="seconds">seconds</option>
                <option value="minutes">minutes</option>
              </select>
            </label>
            <label className="field-label">
              Mail every (minutes)
              <input
                value={mailEvery}
                onChange={(event) => setMailEvery(event.target.value)}
                inputMode="numeric"
                required
              />
            </label>
            <button type="submit" className="btn primary" disabled={busy}>
              Add watch
            </button>
          </form>
        ) : (
          <p className="muted">Only an admin can add or check a watch.</p>
        )}
        {rows.length === 0 ? (
          <p className="muted">No process watches yet.</p>
        ) : (
          <div className="alert-list">
            {rows.map((row) => (
              <article className="alert-item" key={row.id}>
                <span
                  className={`badge ${
                    row.status === 'down' ? 'critical' : row.status === 'up' ? 'ok' : 'pending'
                  }`}
                >
                  {row.status === 'unknown' ? 'not checked' : row.status}
                </span>
                <div className="alert-copy">
                  <div className="alert-title-line">
                    <strong>{watchTitle(row)}</strong>
                    <span className="muted">
                      {row.process_name} · {row.ssh_username}@{row.ip_address}:{row.ssh_port}
                    </span>
                  </div>
                  <p className="alert-message process-countdown">
                    {checkingId === row.id
                      ? 'Checking…'
                      : `Next check in ${countdownText(remainingMs(row, now))}`}
                  </p>
                  <p className="alert-message">
                    {row.recipients.join(', ')} · check every {everyLabel(row.check_interval, row.check_interval_unit)} ·
                    mail every {row.mail_interval_minutes} min · {mailLine(row)}
                    {row.last_checked_at ? ` · checked ${formatWhen(row.last_checked_at)}` : ''}
                  </p>
                  {row.last_error ? <p className="alert-message">{row.last_error}</p> : null}
                </div>
                {isAdmin ? (
                  <div className="alert-actions">
                    <button
                      type="button"
                      className="btn ghost"
                      disabled={checkingId === row.id}
                      onClick={async () => {
                        setCheckingId(row.id)
                        setError(null)
                        try {
                          const updated = await checkProcessWatch(row.id)
                          setRows((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
                        } catch (err) {
                          setError(err instanceof Error ? err.message : 'Process check failed')
                        } finally {
                          setCheckingId(null)
                        }
                      }}
                    >
                      {checkingId === row.id ? 'Checking…' : 'Check now'}
                    </button>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={async () => {
                        setError(null)
                        try {
                          await deleteProcessWatch(row.id)
                          setRows((prev) => prev.filter((item) => item.id !== row.id))
                        } catch (err) {
                          setError(err instanceof Error ? err.message : 'Failed to delete process watch')
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
