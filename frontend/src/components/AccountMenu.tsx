import { useEffect, useRef, useState } from 'react'
import { changePassword, type AppUser } from '../api'

type Props = {
  user: AppUser
  onLogout: () => void
  onOpenUsers?: () => void
}

export function AccountMenu({ user, onLogout, onOpenUsers }: Props) {
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const initials = user.email.slice(0, 2).toUpperCase()
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
        onClick={() => {
          setOpen((value) => !value)
          setMessage(null)
          setError(null)
        }}
      >
        <span className="account-avatar" aria-hidden>
          {initials}
        </span>
        <span className="account-id">
          <strong>{user.email}</strong>
          <span>{role}</span>
        </span>
      </button>
      {open ? (
        <div className="account-panel" role="dialog" aria-label="Account">
          <p className="account-panel-kicker">Profile</p>
          <p className="account-panel-email">{user.email}</p>
          <p className="account-panel-role">{role}</p>
          <button
            type="button"
            className="account-action"
            onClick={() => {
              setSettings((value) => !value)
              setMessage(null)
              setError(null)
            }}
          >
            Settings
          </button>
          {settings ? (
            <form
              className="account-settings"
              onSubmit={async (event) => {
                event.preventDefault()
                setBusy(true)
                setMessage(null)
                setError(null)
                try {
                  await changePassword(currentPassword, newPassword)
                  setCurrentPassword('')
                  setNewPassword('')
                  setMessage('Password updated.')
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Could not update password')
                } finally {
                  setBusy(false)
                }
              }}
            >
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
              {error ? <p className="account-form-error">{error}</p> : null}
              {message ? <p className="account-form-ok">{message}</p> : null}
              <button type="submit" className="btn primary" disabled={busy}>
                {busy ? 'Saving…' : 'Update password'}
              </button>
            </form>
          ) : null}
          {onOpenUsers ? (
            <button
              type="button"
              className="account-action"
              onClick={() => {
                setOpen(false)
                onOpenUsers()
              }}
            >
              Users
            </button>
          ) : null}
          <button type="button" className="account-action account-action--logout" onClick={onLogout}>
            Log out
          </button>
        </div>
      ) : null}
    </div>
  )
}
