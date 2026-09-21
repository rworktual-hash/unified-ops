import { useState } from 'react'
import { login } from '../api'
import { BrandLockup } from './BrandLockup'

type Props = {
  onLoggedIn: () => void
}

export function LoginPage({ onLoggedIn }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand-wrap">
          <BrandLockup variant="login" />
        </div>
        <h1>Sign in</h1>
        <p className="muted">Worktual Observability — use the account your admin created.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            setBusy(true)
            setError(null)
            try {
              await login(email, password)
              onLoggedIn()
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Login failed')
            } finally {
              setBusy(false)
            }
          }}
        >
          <label className="field-label">
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="field-label">
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
          {error && <p className="banner error">{error}</p>}
          <button type="submit" className="btn primary login-submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
