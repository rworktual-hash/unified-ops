import type { Server } from './types'

export type DomainId = 'all' | 'ai' | 'infrastructure' | 'backupvault' | 'email' | 'voicemg' | 'other'

export type DomainDef = {
  id: DomainId
  label: string
  description: string
}

const KNOWN = new Set(['ai', 'infrastructure', 'backupvault', 'email', 'voicemg'])

export function domainForServer(server: Server): DomainId {
  const p = (server.project ?? '').toLowerCase()
  if (p === 'ai') return 'ai'
  if (p === 'infrastructure' || p === 'infra') return 'infrastructure'
  if (p === 'backupvault') return 'backupvault'
  if (p === 'email') return 'email'
  if (p === 'voicemg') return 'voicemg'
  return 'other'
}

export const SERVER_DOMAINS: DomainDef[] = [
  {
    id: 'ai',
    label: 'AI / GPU',
    description: 'GPU pilot hosts (148 & 149). “Devices” = GPUs on that machine from nvidia-smi, not host count.',
  },
  {
    id: 'infrastructure',
    label: 'Infrastructure',
    description: 'Nginx, Kong, DBs, Grafana, PBX, SIP, and platform servers.',
  },
  {
    id: 'backupvault',
    label: 'BackupVault',
    description: 'BackupVault app and database slaves.',
  },
  {
    id: 'email',
    label: 'Email',
    description: 'Email management gateways (SSH queue metrics).',
  },
  {
    id: 'voicemg',
    label: 'VoiceMG',
    description: 'VoiceMG / STT / VMG application hosts.',
  },
  {
    id: 'other',
    label: 'Other',
    description: 'Hosts without a known project tag.',
  },
]

export function serversInDomain(servers: Server[], domain: DomainId): Server[] {
  if (domain === 'all') return servers
  return servers.filter((s) => domainForServer(s) === domain)
}

export function countByDomain(servers: Server[]): Record<DomainId, number> {
  const counts: Record<string, number> = { all: servers.length }
  for (const s of servers) {
    const d = domainForServer(s)
    counts[d] = (counts[d] ?? 0) + 1
  }
  return counts as Record<DomainId, number>
}

export function isKnownProject(project: string | null): boolean {
  return KNOWN.has((project ?? '').toLowerCase())
}
