import { useCallback, useEffect, useState } from 'react'
import { fetchBackupVaultIncremental, type BackupVaultIncremental } from '../api'

export function BackupVaultIncremental() {
  const [data, setData] = useState<BackupVaultIncremental | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchBackupVaultIncremental()
      setData(next)
      if (!next.ok && next.reason) setError(next.reason)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load incremental jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading && !data) return <p className="muted">Loading incremental backups…</p>
  if (error && !data?.ok) return <p className="banner error">{error}</p>
  if (!data) return null

  return (
    <section className="bv-portal">
      <div className="bv-portal-toolbar">
        <div>
          <h2>Incremental backup</h2>
          <p className="muted">
            Last rsync / incremental status from `.222` — view only, no Run all.
            {data.source ? ` · source ${data.source}` : ''}
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <p className="muted bv-sub">
        {data.host ? `Host ${data.host}` : 'Host —'}
        {data.schedule ? ` · ${data.schedule}` : ''}
        {data.last_cycle ? ` · last ${new Date(data.last_cycle).toLocaleString()}` : ''}
      </p>
      <div className="table-wrap bv-runs-table">
        <table>
          <thead>
            <tr>
              <th>Database</th>
              <th>Status</th>
              <th>Last success</th>
              <th>Source file</th>
              <th>Remote</th>
            </tr>
          </thead>
          <tbody>
            {data.jobs.map((job) => (
              <tr key={`${job.id}-${job.name}`}>
                <td>
                  <strong>{job.name}</strong>
                  {job.script ? <div className="muted bv-sub">{job.script}</div> : null}
                </td>
                <td>
                  <span className={`bv-pill bv-pill--${(job.status || 'unknown').toLowerCase()}`}>
                    {(job.status || 'unknown').toUpperCase()}
                  </span>
                </td>
                <td>{job.last_success ? new Date(job.last_success).toLocaleString() : '—'}</td>
                <td>{job.file_size_label || '—'}</td>
                <td className="bv-path">{job.remote_path || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!data.jobs.length ? (
        <p className="muted">No incremental rows on MariaDB `backupvault`.</p>
      ) : null}
    </section>
  )
}
