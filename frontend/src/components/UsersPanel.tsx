import { useCallback, useEffect, useState } from 'react'
import { createUser, listUsers, updateUser, type AppUser } from '../api'

export function UsersPanel() {
  const [users, setUsers] = useState<AppUser[]>([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setUsers(await listUsers())
  }, [])

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : 'Failed to load users'))
  }, [load])

  return (
    <div className="users-page">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Add user</h2>
            <p className="users-lead">They sign in with this email and password.</p>
          </div>
        </div>
        <form
          className="user-add-form"
          onSubmit={async (e) => {
            e.preventDefault()
            setBusy(true)
            setError(null)
            try {
              await createUser({ email, password, role: 'user' })
              setEmail('')
              setPassword('')
              await load()
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Could not add user')
            } finally {
              setBusy(false)
            }
          }}
        >
          <label className="field-label">
            Email
            <input
              type="email"
              autoComplete="off"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="field-label">
            Password
            <input
              type="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
          <button type="submit" className="btn primary" disabled={busy}>
            {busy ? 'Adding…' : 'Add user'}
          </button>
        </form>
        {error && <p className="banner error">{error}</p>}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>People with access</h2>
          <span className="users-count">{users.length}</span>
        </div>
        {users.length === 0 ? (
          <p className="muted">No users yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="users-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="users-email">{u.email}</td>
                    <td>
                      <span className={`users-pill ${u.role === 'admin' ? 'users-pill--admin' : ''}`}>
                        {u.role === 'admin' ? 'Admin' : 'User'}
                      </span>
                    </td>
                    <td>
                      <span className={`users-pill ${u.is_active ? 'users-pill--on' : 'users-pill--off'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="action-cell">
                      {u.is_active && u.role !== 'admin' && (
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={async () => {
                            await updateUser(u.id, { is_active: false })
                            await load()
                          }}
                        >
                          Revoke access
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
