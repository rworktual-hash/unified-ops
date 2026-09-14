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
    <>
      <header className="page-head">
        <h1>Users</h1>
        <p>Add Gmail addresses and passwords for people who may use this dashboard.</p>
      </header>

      <section className="panel">
        <h2>Add user</h2>
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
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field-label">
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
          <button type="submit" className="btn primary" disabled={busy}>
            Add user
          </button>
        </form>
        {error && <p className="banner error">{error}</p>}
      </section>

      <section className="panel">
        <h2>Allowed users ({users.length})</h2>
        {users.length === 0 ? (
          <p className="muted">No users yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Active</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{u.role}</td>
                    <td>{u.is_active ? 'Yes' : 'No'}</td>
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
    </>
  )
}
