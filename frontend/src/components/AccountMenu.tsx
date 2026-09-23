import { useEffect, useRef, useState } from 'react'
import { changePassword, type AppUser } from '../api'

type Props = {
  user: AppUser
  onLogout: () => void
  onOpenUsers?: () => void
}

export function AccountMenu({ user, onLogout, onOpenUsers }: Props) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<'menu' | 'settings'>('menu')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const initial = (user.email.trim()[0] || 'U').toUpperCase()
  const role = user.role === 'admin' ? 'Admin' : 'User'

  useEffect(() => {
    if (!open) return
    function onPointer(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="account-menu" ref={rootRef}>
      <button
        type="button"
        className="account-trigger"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Account ${user.email}`}
        onClick={() => {
          setOpen((value) => !value)
          setView('menu')
          setMessage(null)
          setError(null)
        }}
      >
        <span className="account-avatar" aria-hidden>
          {initial}
          <span className="account-presence" />
        </span>
      </button>
      {open ? (
        <div className="account-panel" role="dialog" aria-label="Account">
          <div className="account-head">
            <span className="account-avatar account-avatar--lg" aria-hidden>
              {initial}
            </span>
            <div>
              <p className="account-panel-email">{user.email}</p>
              <p className="account-panel-role">
                <span className="account-presence account-presence--inline" />
                {role}
                {user.is_active ? ' · Active' : ' · Inactive'}
              </p>
            </div>
          </div>
          {view === 'menu' ? (
            <div className="account-list">
              <button type="button" className="account-action" onClick={() => setView('settings')}>
                <span>Settings</span>
                <span className="account-action-hint">Password and account</span>
              </button>
              {onOpenUsers ? (
                <button
                  type="button"
                  className="account-action"
                  onClick={() => {
                    setOpen(false)
                    onOpenUsers()
                  }}
                >
                  <span>Users</span>
                  <span className="account-action-hint">Who can sign in</span>
                </button>
              ) : null}
              <button type="button" className="account-action account-action--logout" onClick={onLogout}>
                <span>Log out</span>
                <span className="account-action-hint">End this session</span>
              </button>
            </div>
          ) : (
            <form
              className="account-settings"
              onSubmit={async (event) => {
                event.preventDefault()
                if (newPassword !== confirmPassword) {
                  setError('New password and confirmation do not match.')
                  setMessage(null)
                  return
                }
                setBusy(true)
                setMessage(null)
                setError(null)
                try {
                  await changePassword(currentPassword, newPassword)
                  setCurrentPassword('')
                  setNewPassword('')
                  setConfirmPassword('')
                  setMessage('Password updated.')
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Could not update password')
                } finally {
                  setBusy(false)
                }
              }}
            >
              <button type="button" className="account-back" onClick={() => setView('menu')}>
                Back
              </button>
              <p className="account-section">Account</p>
              <dl className="account-facts">
                <div>
                  <dt>Email</dt>
                  <dd>{user.email}</dd>
                </div>
                <div>
                  <dt>Role</dt>
                  <dd>{role}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{user.is_active ? 'Active' : 'Inactive'}</dd>
                </div>
              </dl>
              <p className="account-section">Security</p>
              <label className="field-label">
                Current password
                <input
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </label>
              <label className="field-label">
                New password
                <input
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </label>
              <label className="field-label">
                Confirm new password
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </label>
              {error ? <p className="account-form-error">{error}</p> : null}
              {message ? <p className="account-form-ok">{message}</p> : null}
              <button type="submit" className="btn primary" disabled={busy}>
                {busy ? 'Saving…' : 'Update password'}
              </button>
            </form>
          )}
        </div>
      ) : null}
    </div>
  )
}
