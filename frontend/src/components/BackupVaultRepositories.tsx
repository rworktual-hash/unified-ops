import { useCallback, useEffect, useState } from 'react'
import { fetchBackupVaultRepositories, type BackupVaultRepoTier } from '../api'

export function BackupVaultRepositories() {
  const [tiers, setTiers] = useState<BackupVaultRepoTier[]>([])
  const [source, setSource] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchBackupVaultRepositories()
      setTiers(next.tiers)
      setSource(next.source ?? null)
      if (!next.ok && next.reason) setError(next.reason)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load repositories')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="bv-repo-wrap">
      <div className="bv-portal-toolbar">
        <div>
          <h3 className="bv-group-title">Repository hierarchy</h3>
          <p className="muted">
            Latest dump per database from `.222` — read-only file catalog, not SFTP browse.
            {source ? ` · ${source}` : ''}
          </p>
        </div>
        <button type="button" className="btn ghost" disabled={loading} onClick={() => void load()}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      {error ? <p className="banner error">{error}</p> : null}
      {tiers.map((tier) => (
        <article key={tier.id} className="bv-repo-tier">
          <h3 className="bv-group-title">
            {tier.label} · {tier.folder_count} databases · {tier.file_count} files
            {tier.bytes_label ? ` · ${tier.bytes_label}` : ''}
          </h3>
          <div className="table-wrap bv-runs-table">
            <table>
              <thead>
                <tr>
                  <th>Folder</th>
                  <th>Latest file</th>
                  <th>Size</th>
                  <th>Modified</th>
                  <th>Files</th>
                </tr>
              </thead>
              <tbody>
                {tier.folders.map((folder) => (
                  <tr key={`${tier.id}-${folder.name}`}>
                    <td>
                      <strong>{folder.name}</strong>
                    </td>
                    <td className="bv-path">{folder.latest_file || folder.file_path || '—'}</td>
                    <td>{folder.file_size_label || '—'}</td>
                    <td>{folder.modified_at ? new Date(folder.modified_at).toLocaleString() : '—'}</td>
                    <td>{folder.file_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ))}
      {!tiers.length && !loading ? (
        <p className="muted">No dump catalog rows on MariaDB `backupvault`.</p>
      ) : null}
    </div>
  )
}
