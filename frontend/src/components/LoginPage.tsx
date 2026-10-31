import { useState } from 'react'
import { login } from '../api'
import { BrandLockup } from './BrandLockup'

type Props = {
  onLoggedIn: () => void
}

const POINTS = [
  {
    title: 'Servers & hosts',
    text: 'Live status across the fleet.',
    icon: 'servers',
  },
  {
    title: 'Process monitor',
    text: 'PID, countdown, and down or up mail.',
    icon: 'process',
  },
  {
    title: 'Alerts',
    text: 'Open incidents in one list.',
    icon: 'alerts',
  },
  {
    title: 'Infrastructure',
    text: 'Voice, mail, backup, and LLM traces.',
    icon: 'infra',
  },
] as const

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
      <main className="login-stage">
        <section className="login-hero" aria-label="Worktual Observability">
          <img src="/worktual-logo.png" alt="Worktual" className="login-hero-logo" />
          <h1>
            <span>Observability</span>
            &amp; operations hub for servers, services, and alerts
          </h1>
          <p>Watch hosts, processes, mail, voice, and backups from one workspace.</p>
          <ul>
            {POINTS.map((point) => (
              <li key={point.title}>
                <PointIcon name={point.icon} />
                <span>
                  <strong>{point.title}</strong>
                  {point.text}
                </span>
              </li>
            ))}
          </ul>
        </section>
        <form
          className="login-card"
          onSubmit={async (event) => {
            event.preventDefault()
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
          <h2>Welcome back</h2>
          <p className="login-lead">Use the work email and password issued for your role.</p>
          <label className="login-field">
            Email
            <span className="login-control">
              <MailIcon />
              <input
                type="email"
                autoComplete="username"
                placeholder="name@worktual.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </span>
          </label>
          <label className="login-field">
            Password
            <span className="login-control">
              <LockIcon />
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
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
            </span>
          </label>
          <label className="login-remember">
            <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
            Remember me
          </label>
          {error ? <p className="banner error login-error">{error}</p> : null}
          <button type="submit" className="login-submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
            {busy ? null : <span aria-hidden="true">→</span>}
          </button>
        </form>
      </main>
      <footer className="login-foot">
        <span>Secure sign-in</span>
        <span>Role-based access</span>
        <span>Live process alerts</span>
      </footer>
    </div>
  )
}

function PointIcon({ name }: { name: (typeof POINTS)[number]['icon'] }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === 'servers' ? (
        <>
          <rect x="3" y="4" width="18" height="6" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <rect x="3" y="14" width="18" height="6" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <circle cx="7" cy="7" r="0.8" fill="currentColor" />
          <circle cx="7" cy="17" r="0.8" fill="currentColor" />
        </>
      ) : null}
      {name === 'process' ? (
        <>
          <circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M12 8v4l3 2" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </>
      ) : null}
      {name === 'alerts' ? (
        <path
          d="M12 4l8 14H4L12 4z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
      ) : null}
      {name === 'infra' ? (
        <>
          <rect x="4" y="4" width="7" height="7" rx="1.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <rect x="13" y="4" width="7" height="7" rx="1.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <rect x="4" y="13" width="7" height="7" rx="1.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <rect x="13" y="13" width="7" height="7" rx="1.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </>
      ) : null}
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
