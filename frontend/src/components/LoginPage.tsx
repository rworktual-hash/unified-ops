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
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function blockProvider(name: string) {
    setError(null)
    setNotice(`Your network is not allowed to continue with ${name}.`)
  }

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
            setNotice(null)
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

          <div className="login-providers">
            <button type="button" className="login-provider login-provider--google" onClick={() => blockProvider('Google')}>
              <GoogleIcon />
              Continue with Google
            </button>
            <button type="button" className="login-provider login-provider--microsoft" onClick={() => blockProvider('Microsoft')}>
              <MicrosoftIcon />
              Continue with Microsoft
            </button>
            <button type="button" className="login-provider login-provider--apple" onClick={() => blockProvider('Apple')}>
              <AppleIcon />
              Continue with Apple
            </button>
          </div>
          {notice ? <p className="login-notice">{notice}</p> : null}
          <p className="login-or">or</p>

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

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#fff" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3z" />
      <path fill="#fff" d="M12 22c2.7 0 5-0.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22z" />
      <path fill="#fff" d="M6.4 13.9a6 6 0 0 1 0-3.8V7.5H3.1a10 10 0 0 0 0 9l3.3-2.6z" />
      <path fill="#fff" d="M12 6c1.5 0 2.8.5 3.8 1.5l2.8-2.8A10 10 0 0 0 3.1 7.5l3.3 2.6C7.2 7.8 9.4 6 12 6z" />
    </svg>
  )
}

function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#f25022" d="M3 3h8.5v8.5H3z" />
      <path fill="#7fba00" d="M12.5 3H21v8.5h-8.5z" />
      <path fill="#00a4ef" d="M3 12.5h8.5V21H3z" />
      <path fill="#ffb900" d="M12.5 12.5H21V21h-8.5z" />
    </svg>
  )
}

function AppleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#fff"
        d="M16.4 12.6c0-2.2 1.8-3.3 1.9-3.4-1-1.5-2.6-1.7-3.2-1.7-1.3-.1-2.6.8-3.3.8s-1.7-.8-2.8-.8c-1.5 0-2.8.8-3.6 2.1-1.5 2.7-.4 6.6 1.1 8.8.7 1.1 1.6 2.3 2.7 2.2 1.1 0 1.5-.7 2.8-.7s1.6.7 2.8.7 1.9-1.1 2.6-2.1c.8-1.2 1.1-2.3 1.2-2.4-.1 0-2.2-.8-2.2-3.5zM14.7 6.6c.6-.7 1-1.7.9-2.6-.9 0-1.9.6-2.5 1.3-.6.6-1.1 1.6-.9 2.5 1 .1 1.9-.5 2.5-1.2z"
      />
    </svg>
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
