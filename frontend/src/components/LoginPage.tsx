import { useState } from 'react'
import { login } from '../api'
import { BrandLockup } from './BrandLockup'

type Props = {
  onLoggedIn: () => void
}

export function LoginPage({ onLoggedIn }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  return (
    <div className="login-shell">
      <header className="login-topbar">
        <BrandLockup variant="login" />
      </header>
      <main className="login-main">
        <form
          className="login-form"
          onSubmit={async (e) => {
            e.preventDefault()
            setBusy(true)
            setError(null)
            try {
              await login(email, password, remember)
              onLoggedIn()
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Login failed')
            } finally {
              setBusy(false)
            }
          }}
        >
          <h1>Log in to Your Account</h1>
          <p className="login-lead">to access Worktual Observability</p>

          <label className="login-field">
            <span className="sr-only">Email</span>
            <MailIcon />
            <input
              type="email"
              autoComplete="username"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="login-field">
            <span className="sr-only">Password</span>
            <LockIcon />
            <input
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
            <button
              type="button"
              className="login-eye"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              onClick={() => setShowPassword((open) => !open)}
            >
              <EyeIcon off={showPassword} />
            </button>
          </label>

          <label className="login-remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            Keep me logged in
          </label>

          {error ? <p className="banner error login-error">{error}</p> : null}

          <button type="submit" className="login-submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Login'}
          </button>
        </form>
      </main>
    </div>
  )
}

function MailIcon() {
  return (
    <svg className="login-field-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4 7l8 6 8-6" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function LockIcon() {
  return (
    <svg className="login-field-icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="11" width="14" height="9" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle cx="12" cy="12" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      {off ? <path d="M5 19L19 5" stroke="currentColor" strokeWidth="1.6" /> : null}
    </svg>
  )
}
