import type { Server } from '../types'

export type FleetGroupId =
  | 'all'
  | 'ai'
  | 'infrastructure'
  | 'redis'
  | 'email'
  | 'backupvault'
  | 'voicemg'

export type FleetGroupDef = {
  id: FleetGroupId
  label: string
  emptyHint?: string
}

export const FLEET_GROUPS: FleetGroupDef[] = [
  { id: 'all', label: 'All servers' },
  { id: 'ai', label: 'AI / GPU' },
  { id: 'infrastructure', label: 'Infrastructure' },
  { id: 'redis', label: 'Redis' },
  { id: 'email', label: 'Email' },
  { id: 'backupvault', label: 'BackupVault & DB slaves' },
  {
    id: 'voicemg',
    label: 'Voice MG',
    emptyHint: 'Voice MG dashboards will be added in a later release.',
  },
]

export function serverMatchesFleetGroup(server: Server, group: FleetGroupId): boolean {
  if (group === 'all') return true
  if (group === 'ai') return server.project === 'ai'
  if (group === 'voicemg') return server.project === 'voicemg'
  if (group === 'email') return server.project === 'email'
  if (group === 'backupvault') return server.project === 'backupvault'
  if (group === 'redis') return server.server_type === 'redis'
  if (group === 'infrastructure') {
    return server.project === 'infrastructure' && server.server_type !== 'redis'
  }
  return true
}

export function countInGroup(servers: Server[], group: FleetGroupId, activeOnly: boolean): number {
  const pool = activeOnly ? servers.filter((s) => s.is_active) : servers
  return pool.filter((s) => serverMatchesFleetGroup(s, group)).length
}
