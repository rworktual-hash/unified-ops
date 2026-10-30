import { useCallback, useEffect, useState } from 'react'
import {
  checkProcessWatch,
  createProcessWatch,
  deleteProcessWatch,
  listProcessWatches,
  type ProcessWatch,
} from '../api'
import { formatWhen } from '../formatWhen'

type Props = {
  isAdmin: boolean
}

function mailLine(row: ProcessWatch): string {
  if (row.mail_sent === false) return row.mail_error || 'Mail was not sent'
  if (row.mail_sent && row.last_emailed_at) return `Mail sent ${formatWhen(row.last_emailed_at)}`
  return 'No mail yet'
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
                  <strong>{row.process_name}</strong>
                  <span className="muted">{row.ip_address}</span>
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
  const [processName, setProcessName] = useState('')
  const [recipients, setRecipients] = useState('')
  const [interval, setIntervalMinutes] = useState('5')

  const load = useCallback(async () => {
    setRows(await listProcessWatches())
  }, [])

  useEffect(() => {
    void load().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to load process watches')
    })
  }, [load])

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Watches</h2>
            <p className="muted-block">
              SSH checks the process about once a minute. Mail repeats on the interval you set until
              the process is running again.
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
                  process_name: processName.trim(),
                  recipients: recipients.split(/[,;\s]+/).filter(Boolean),
                  mail_interval_minutes: Number(interval),
                })
                setIp('')
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
              Mail every (minutes)
              <input
                value={interval}
                onChange={(event) => setIntervalMinutes(event.target.value)}
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
                    <strong>{row.process_name}</strong>
                    <span className="muted">
                      {row.ssh_username}@{row.ip_address}:{row.ssh_port}
                    </span>
                  </div>
                  <p className="alert-message">
                    {row.recipients.join(', ')} · mail every {row.mail_interval_minutes} min ·{' '}
                    {mailLine(row)}
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
