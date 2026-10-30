import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkProcessWatch,
  createProcessWatch,
  deleteProcessWatch,
  listProcessWatches,
  updateProcessWatch,
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

function remainingMs(row: ProcessWatch, clientNow: number, clockOffset: number): number {
  const checked = parseWhen(row.last_checked_at)
  if (checked == null) return 0
  return Math.max(0, checked + intervalMs(row) - (clientNow + clockOffset))
}

function rowDetail(row: ProcessWatch): string {
  return [
    row.recipients.join(', '),
    `check every ${everyLabel(row.check_interval, row.check_interval_unit)}`,
    `mail every ${row.mail_interval_minutes} min`,
    mailLine(row),
    row.last_checked_at ? `checked ${formatWhen(row.last_checked_at)}` : '',
    row.last_error ?? '',
  ]
    .filter(Boolean)
    .join(' · ')
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
  const open = watches.filter((row) => row.enabled && row.status === 'down')
  const resolved = watches.filter((row) => row.enabled && row.status === 'up' && row.resolved_at)
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
  const [description, setDescription] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [processName, setProcessName] = useState('')
  const [recipients, setRecipients] = useState('')
  const [checkEvery, setCheckEvery] = useState('60')
  const [checkUnit, setCheckUnit] = useState<'seconds' | 'minutes'>('seconds')
  const [mailEvery, setMailEvery] = useState('5')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [menuId, setMenuId] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const inFlight = useRef<Set<number>>(new Set())
  const retryAt = useRef<Record<number, number>>({})
  const clockOffset = useRef(0)

  function noteServerTime(sample: ProcessWatch | undefined) {
    const server = parseWhen(sample?.server_now)
    if (server != null) clockOffset.current = server - Date.now()
  }

  const load = useCallback(async () => {
    const next = await listProcessWatches()
    noteServerTime(next[0])
    setRows(next)
  }, [])

  function closeForm() {
    setShowForm(false)
    setEditingId(null)
    setIp('')
    setPort('22')
    setUsername('root')
    setPassword('')
    setLabel('')
    setDescription('')
    setEnabled(true)
    setProcessName('')
    setRecipients('')
    setCheckEvery('60')
    setCheckUnit('seconds')
    setMailEvery('5')
  }

  function openAdd() {
    closeForm()
    setShowForm(true)
  }

  function openEdit(row: ProcessWatch) {
    setEditingId(row.id)
    setLabel(row.label)
    setDescription(row.description)
    setEnabled(row.enabled)
    setIp(row.ip_address)
    setPort(String(row.ssh_port))
    setUsername(row.ssh_username)
    setPassword('')
    setProcessName(row.process_name)
    setRecipients(row.recipients.join(', '))
    setCheckEvery(String(row.check_interval))
    setCheckUnit(row.check_interval_unit === 'minutes' ? 'minutes' : 'seconds')
    setMailEvery(String(row.mail_interval_minutes))
    setShowForm(true)
    setError(null)
  }

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
        .then((next) => {
          noteServerTime(next[0])
          setRows(next)
        })
        .catch(() => undefined)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!isAdmin) return
    for (const row of rows) {
      if (!row.enabled) continue
      if (inFlight.current.has(row.id)) continue
      if ((retryAt.current[row.id] ?? 0) > now) continue
      if (remainingMs(row, now, clockOffset.current) > 0) continue
      inFlight.current.add(row.id)
      setCheckingId(row.id)
      void checkProcessWatch(row.id)
        .then((updated) => {
          noteServerTime(updated)
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

  useEffect(() => {
    if (menuId == null) return
    function close() {
      setMenuId(null)
    }
    window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [menuId])

  const needle = query.trim().toLowerCase()
  const shown = needle
    ? rows.filter((row) =>
        [row.label, row.process_name, row.pid, row.description, row.ip_address, row.status, row.ssh_username]
          .join(' ')
          .toLowerCase()
          .includes(needle),
      )
    : rows

  return (
    <>
      <section className="panel">
        <div className="panel-head process-head">
          <div>
            <h2>Watches</h2>
            <p className="muted-block">
              Each active watch checks itself when its timer reaches zero. The timer uses the server clock,
              so every open session counts down together. Mail repeats on the mail interval while the process stays down.
            </p>
          </div>
          {isAdmin ? (
            <button type="button" className="btn primary" onClick={openAdd}>
              Add service
            </button>
          ) : null}
        </div>
        {error ? <p className="banner error">{error}</p> : null}
        {isAdmin && showForm ? (
          <form
            className="process-create"
            onSubmit={async (event) => {
              event.preventDefault()
              setBusy(true)
              setError(null)
              try {
                const body = {
                  ip_address: ip.trim(),
                  ssh_port: Number(port),
                  ssh_username: username.trim() || 'root',
                  ssh_password: password,
                  label: label.trim(),
                  description: description.trim(),
                  process_name: processName.trim(),
                  enabled,
                  recipients: recipients.split(/[,;\s]+/).filter(Boolean),
                  check_interval: Number(checkEvery),
                  check_interval_unit: checkUnit,
                  mail_interval_minutes: Number(mailEvery),
                }
                if (editingId == null) {
                  const created = await createProcessWatch(body)
                  setRows((prev) => [created, ...prev.filter((row) => row.id !== created.id)])
                } else {
                  const updated = await updateProcessWatch(editingId, body)
                  setRows((prev) => prev.map((row) => (row.id === updated.id ? updated : row)))
                }
                closeForm()
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to save process watch')
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
            <label className="field-label process-description">
              Description
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this service does"
                rows={3}
              />
            </label>
            <label className="process-switch-field">
              <button
                type="button"
                className={`process-switch ${enabled ? 'on' : ''}`}
                aria-pressed={enabled}
                onClick={() => setEnabled((current) => !current)}
              >
                <span />
              </button>
              {enabled ? 'Active' : 'Inactive'}
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
                required={editingId == null}
                placeholder={editingId == null ? '' : 'Leave blank to keep the current password'}
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
              {editingId == null ? 'Add service' : 'Save'}
            </button>
            <button type="button" className="btn ghost" disabled={busy} onClick={closeForm}>
              Cancel
            </button>
          </form>
        ) : null}
        {!isAdmin ? <p className="muted">Only an admin can add or edit a watch.</p> : null}
        <input
          className="process-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search label, process, or IP"
          aria-label="Search watches"
        />
        {rows.length === 0 ? (
          <p className="muted">No process watches yet.</p>
        ) : shown.length === 0 ? (
          <p className="muted">No matching watches.</p>
        ) : (
          <div className="table-wrap">
            <table className="process-table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Process name</th>
                  <th>PID</th>
                  <th>Status</th>
                  <th>Next check</th>
                  <th>Active</th>
                  {isAdmin ? <th aria-label="Actions" /> : null}
                </tr>
              </thead>
              <tbody>
                {shown.map((row) => (
                  <tr key={row.id} title={rowDetail(row)}>
                    <td>
                      <strong>{watchTitle(row)}</strong>
                    </td>
                    <td>{row.process_name}</td>
                    <td className="process-pid">{row.status === 'up' && row.pid ? row.pid : '—'}</td>
                    <td>
                      <span
                        className={`badge ${
                          row.status === 'down' ? 'critical' : row.status === 'up' ? 'ok' : 'pending'
                        }`}
                      >
                        {row.status === 'unknown' ? 'not checked' : row.status}
                      </span>
                    </td>
                    <td className="process-countdown">
                      {!row.enabled
                        ? 'Inactive'
                        : checkingId === row.id
                          ? 'Checking…'
                          : countdownText(remainingMs(row, now, clockOffset.current))}
                    </td>
                    <td>
                      {isAdmin ? (
                        <button
                          type="button"
                          className={`process-switch ${row.enabled ? 'on' : ''}`}
                          aria-pressed={row.enabled}
                          onClick={async () => {
                            setError(null)
                            try {
                              const updated = await updateProcessWatch(row.id, {
                                ip_address: row.ip_address,
                                ssh_port: row.ssh_port,
                                ssh_username: row.ssh_username,
                                ssh_password: '',
                                label: row.label,
                                description: row.description,
                                process_name: row.process_name,
                                recipients: row.recipients,
                                check_interval: row.check_interval,
                                check_interval_unit: row.check_interval_unit,
                                mail_interval_minutes: row.mail_interval_minutes,
                                enabled: !row.enabled,
                              })
                              noteServerTime(updated)
                              setRows((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
                            } catch (err) {
                              setError(err instanceof Error ? err.message : 'Failed to update process watch')
                            }
                          }}
                        >
                          <span />
                          {row.enabled ? 'Active' : 'Inactive'}
                        </button>
                      ) : (
                        <span className="muted">{row.enabled ? 'Active' : 'Inactive'}</span>
                      )}
                    </td>
                    {isAdmin ? (
                      <td className="process-menu">
                        <button
                          type="button"
                          className="process-menu-btn"
                          aria-label={`Actions for ${watchTitle(row)}`}
                          aria-expanded={menuId === row.id}
                          onClick={(event) => {
                            event.stopPropagation()
                            setMenuId((current) => (current === row.id ? null : row.id))
                          }}
                        >
                          ···
                        </button>
                        {menuId === row.id ? (
                          <div className="process-menu-pop" onClick={(event) => event.stopPropagation()}>
                            <button
                              type="button"
                              onClick={() => {
                                setMenuId(null)
                                openEdit(row)
                              }}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              disabled={!row.enabled || checkingId === row.id}
                              onClick={async () => {
                                setMenuId(null)
                                setCheckingId(row.id)
                                setError(null)
                                try {
                                  const updated = await checkProcessWatch(row.id, { force: true })
                                  noteServerTime(updated)
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
                              onClick={async () => {
                                setMenuId(null)
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
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
