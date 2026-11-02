import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkProcessWatch,
  createProcessWatch,
  deleteProcessWatch,
  getDefaultProcessMails,
  listProcessWatchChanges,
  listProcessWatches,
  saveDefaultProcessMails,
  updateProcessWatch,
  type ProcessWatch,
  type ProcessWatchChange,
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

function intervalMs(row: ProcessWatch): number {
  return row.check_interval_unit === 'minutes' ? row.check_interval * 60_000 : row.check_interval * 1000
}

function remainingMs(row: ProcessWatch, clientNow: number, clockOffset: number): number {
  const checked = parseWhen(row.last_checked_at)
  if (checked == null) return 0
  return Math.max(0, checked + intervalMs(row) - (clientNow + clockOffset))
}

function mailsAlreadyDefault(additional: string, defaults: string): string[] {
  const known = new Set(
    defaults
      .split(/[,;\s]+/)
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean),
  )
  const overlap: string[] = []
  const seen = new Set<string>()
  for (const part of additional.split(/[,;\s]+/)) {
    const address = part.trim().toLowerCase()
    if (!address || seen.has(address)) continue
    seen.add(address)
    if (known.has(address)) overlap.push(address)
  }
  return overlap
}

function duplicateMailMessage(overlap: string[]): string {
  const listed = overlap.join(', ')
  const verb = overlap.length === 1 ? 'is' : 'are'
  return `${listed} ${verb} already in the default mail ids. Remove from additional mail ids.`
}

type SortKey = 'label' | 'process_name' | 'ip_address' | 'service_port' | 'pid'

function statusKind(row: ProcessWatch): 'up' | 'down' | 'unknown' {
  if (!row.enabled || row.status === 'unknown') return 'unknown'
  if (row.status === 'down') return 'down'
  if (row.status === 'up') return 'up'
  return 'unknown'
}

function displayedColumn(row: ProcessWatch, key: SortKey): string {
  if (key === 'label') return (row.label.trim() || row.process_name).trim()
  if ((key === 'service_port' || key === 'pid') && (!row.enabled || row.status !== 'up')) return ''
  return String(row[key] ?? '').trim()
}

function sortToken(row: ProcessWatch, key: SortKey): string | number {
  const text = displayedColumn(row, key)
  if (!text) return ''
  if (key === 'pid') {
    const value = Number(text)
    return Number.isFinite(value) ? value : text
  }
  if (key === 'service_port') {
    const value = Number(text.split(/[,\s]+/)[0])
    return Number.isFinite(value) ? value : text
  }
  if (key === 'ip_address') return text.split('.').map((part) => part.padStart(3, '0')).join('.')
  return text
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
  const [formError, setFormError] = useState<string | null>(null)
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
  const [defaultMails, setDefaultMails] = useState('')
  const [savingDefaults, setSavingDefaults] = useState(false)
  const [mailSaved, setMailSaved] = useState(false)
  const [mailError, setMailError] = useState<string | null>(null)
  const [tab, setTab] = useState<'watches' | 'mails' | 'changes'>('watches')
  const [changes, setChanges] = useState<ProcessWatchChange[]>([])
  const [sortKey, setSortKey] = useState<SortKey | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [statusFilter, setStatusFilter] = useState<'all' | 'up' | 'down' | 'unknown'>('all')
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [menuId, setMenuId] = useState<number | null>(null)
  const [menuUp, setMenuUp] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const inFlight = useRef<Set<number>>(new Set())
  const retryAt = useRef<Record<number, number>>({})
  const clockOffset = useRef(0)
  const formRef = useRef<HTMLFormElement>(null)
  const [formScroll, setFormScroll] = useState(0)

  function noteServerTime(sample: ProcessWatch | undefined) {
    const server = parseWhen(sample?.server_now)
    if (server != null) clockOffset.current = server - Date.now()
  }

  const loadChanges = useCallback(async () => {
    setChanges(await listProcessWatchChanges())
  }, [])

  const load = useCallback(async () => {
    const [next, defaults] = await Promise.all([listProcessWatches(), getDefaultProcessMails(), loadChanges()])
    noteServerTime(next[0])
    setRows(next)
    setDefaultMails(defaults.join(', '))
  }, [loadChanges])

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
    setFormError(null)
  }

  function openAdd() {
    closeForm()
    setShowForm(true)
    setFormScroll((tick) => tick + 1)
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
    setFormError(null)
    setFormScroll((tick) => tick + 1)
  }

  useEffect(() => {
    if (!showForm) return
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [showForm, formScroll])

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
  const filtered = rows.filter((row) => {
    if (needle) {
      const haystack = [row.label, row.process_name, row.pid, row.service_port, row.description, row.ip_address, row.status, row.ssh_username]
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(needle)) return false
    }
    if (statusFilter !== 'all' && statusKind(row) !== statusFilter) return false
    if (activeFilter === 'active' && !row.enabled) return false
    if (activeFilter === 'inactive' && row.enabled) return false
    return true
  })
  const shown = sortKey
    ? [...filtered].sort((left, right) => {
        const leftValue = sortToken(left, sortKey)
        const rightValue = sortToken(right, sortKey)
        if (leftValue === '' && rightValue === '') return 0
        if (leftValue === '') return 1
        if (rightValue === '') return -1
        const result =
          typeof leftValue === 'number' && typeof rightValue === 'number'
            ? leftValue - rightValue
            : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' })
        return sortDir === 'asc' ? result : -result
      })
    : filtered

  function columnHead(key: SortKey, title: string) {
    return (
      <th>
        <span className="process-sort-label">{title}</span>
        <span className="process-sort-arrows">
          <button
            type="button"
            className={sortKey === key && sortDir === 'asc' ? 'process-arrow on' : 'process-arrow'}
            aria-label={`Sort ${title} ascending`}
            onClick={() => {
              setSortKey(key)
              setSortDir('asc')
            }}
          >
            ↑
          </button>
          <button
            type="button"
            className={sortKey === key && sortDir === 'desc' ? 'process-arrow on' : 'process-arrow'}
            aria-label={`Sort ${title} descending`}
            onClick={() => {
              setSortKey(key)
              setSortDir('desc')
            }}
          >
            ↓
          </button>
        </span>
      </th>
    )
  }

  return (
    <>
      {isAdmin ? (
        <nav className="bv-tabs process-tabs" aria-label="Process Monitor">
          <button
            type="button"
            className={tab === 'watches' ? 'bv-tab active' : 'bv-tab'}
            onClick={() => setTab('watches')}
          >
            Watches
          </button>
          <button
            type="button"
            className={tab === 'mails' ? 'bv-tab active' : 'bv-tab'}
            onClick={() => setTab('mails')}
          >
            Default mail ids
          </button>
          <button
            type="button"
            className={tab === 'changes' ? 'bv-tab active' : 'bv-tab'}
            onClick={() => setTab('changes')}
          >
            Latest changes
          </button>
        </nav>
      ) : null}
      {tab === 'mails' && isAdmin ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Default mail ids</h2>
              <p className="muted-block">Every process-down alert is sent to these addresses.</p>
            </div>
          </div>
          <form
            className="process-mail-form"
            onSubmit={async (event) => {
              event.preventDefault()
              setSavingDefaults(true)
              setMailError(null)
              setMailSaved(false)
              try {
                const saved = await saveDefaultProcessMails(defaultMails.split(/[,;\s]+/).filter(Boolean))
                setDefaultMails(saved.join(', '))
                setMailSaved(true)
              } catch (err) {
                setMailError(err instanceof Error ? err.message : 'Failed to save default mail ids')
              } finally {
                setSavingDefaults(false)
              }
            }}
          >
            <label className="field-label">
              Mail ids
              <input
                value={defaultMails}
                onChange={(event) => {
                  setDefaultMails(event.target.value)
                  setMailSaved(false)
                }}
                placeholder="a@worktual.com, b@worktual.com"
              />
            </label>
            <button
              type="submit"
              className={mailSaved ? 'btn process-mail-done' : 'btn primary'}
              disabled={savingDefaults}
            >
              {savingDefaults ? 'Saving…' : mailSaved ? 'Saved' : 'Save'}
            </button>
            {mailError ? <p className="banner error process-form-error">{mailError}</p> : null}
          </form>
        </section>
      ) : null}
      {tab === 'changes' && isAdmin ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Latest changes</h2>
              <p className="muted-block">Edits to a service. Checks and countdowns are not listed.</p>
            </div>
          </div>
          {changes.length === 0 ? (
            <p className="muted">No edits yet.</p>
          ) : (
            <ul className="process-changes">
              {changes.map((change) => (
                <li key={change.id}>
                  <div>
                    <strong>{change.label || 'Service'}</strong>
                    <time>{formatWhen(change.created_at)}</time>
                  </div>
                  <p>{change.summary}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      {tab === 'watches' || !isAdmin ? (
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
            ref={formRef}
            className="process-create"
            onSubmit={async (event) => {
              event.preventDefault()
              const overlap = mailsAlreadyDefault(recipients, defaultMails)
              if (overlap.length > 0) {
                setFormError(duplicateMailMessage(overlap))
                return
              }
              setBusy(true)
              setFormError(null)
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
                void loadChanges()
              } catch (err) {
                setFormError(err instanceof Error ? err.message : 'Failed to save process watch')
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
              Additional mail ids
              <input
                value={recipients}
                onChange={(event) => {
                  setRecipients(event.target.value)
                  setFormError(null)
                }}
                placeholder="Extra addresses for this service"
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
            {formError ? <p className="banner error process-form-error">{formError}</p> : null}
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
        ) : (
          <div className="table-wrap">
            <table className="process-table">
              <thead>
                <tr>
                  {columnHead('label', 'Label')}
                  {columnHead('process_name', 'Process name')}
                  {columnHead('ip_address', 'Server')}
                  {columnHead('service_port', 'Service port')}
                  {columnHead('pid', 'PID')}
                  <th>
                    Status
                    <select
                      className="process-filter"
                      aria-label="Filter status"
                      value={statusFilter}
                      onChange={(event) => setStatusFilter(event.target.value as 'all' | 'up' | 'down' | 'unknown')}
                    >
                      <option value="all">All</option>
                      <option value="up">Up</option>
                      <option value="down">Down</option>
                      <option value="unknown">Not checked</option>
                    </select>
                  </th>
                  <th>Next check</th>
                  <th>
                    Active
                    <select
                      className="process-filter"
                      aria-label="Filter active"
                      value={activeFilter}
                      onChange={(event) => setActiveFilter(event.target.value as 'all' | 'active' | 'inactive')}
                    >
                      <option value="all">All</option>
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </th>
                  {isAdmin ? <th aria-label="Actions" /> : null}
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 ? (
                  <tr>
                    <td className="muted process-empty" colSpan={isAdmin ? 9 : 8}>
                      No matching watches. Choose All to see every service.
                    </td>
                  </tr>
                ) : null}
                {shown.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{watchTitle(row)}</strong>
                    </td>
                    <td>{row.process_name}</td>
                    <td className="process-server">{row.ip_address}</td>
                    <td className="process-pid">
                      {row.enabled && row.status === 'up' && row.service_port ? row.service_port : '—'}
                    </td>
                    <td className="process-pid">{row.enabled && row.status === 'up' && row.pid ? row.pid : '—'}</td>
                    <td>
                      <span
                        className={`badge ${
                          !row.enabled || row.status === 'unknown'
                            ? 'pending'
                            : row.status === 'down'
                              ? 'critical'
                              : row.status === 'up'
                                ? 'ok'
                                : 'pending'
                        }`}
                      >
                        {!row.enabled || row.status === 'unknown' ? 'not checked' : row.status}
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
                              void loadChanges()
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
                      <td className={menuId === row.id ? 'process-menu open' : 'process-menu'}>
                        <button
                          type="button"
                          className="process-menu-btn"
                          aria-label={`Actions for ${watchTitle(row)}`}
                          aria-expanded={menuId === row.id}
                          onClick={(event) => {
                            event.stopPropagation()
                            if (menuId === row.id) {
                              setMenuId(null)
                              return
                            }
                            const rect = event.currentTarget.getBoundingClientRect()
                            setMenuUp(window.innerHeight - rect.bottom < 160)
                            setMenuId(row.id)
                          }}
                        >
                          ···
                        </button>
                        {menuId === row.id ? (
                          <div
                            className={menuUp ? 'process-menu-pop up' : 'process-menu-pop'}
                            onClick={(event) => event.stopPropagation()}
                          >
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
                                  void loadChanges()
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
      ) : null}
    </>
  )
}
