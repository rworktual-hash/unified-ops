import { useEffect, useState } from 'react'
import {
  fetchBackupVaultOverview,
  fetchEmailSshOverview,
  fetchInfrastructureOverview,
  fetchVoiceMgOverview,
  type BackupVaultSnapshot,
  type EmailSshSnapshot,
  type InfrastructureSnapshot,
  type VoiceMgSnapshot,
} from '../api'
import type { Server } from '../types'

type Chip = { label: string; up: boolean }

function add(chips: Chip[], label: string, value: boolean | null | undefined) {
  if (value == null) return
  chips.push({ label, up: value })
}

function fromInfrastructure(snap: InfrastructureSnapshot): Chip[] {
  const chips: Chip[] = []
  if (snap.role === 'nginx' || snap.role === 'kafka') {
    add(chips, 'Nginx', snap.nginx_active)
  } else if (snap.role === 'kong') {
    add(chips, 'Kong', snap.kong_active ?? snap.service_active)
  } else if (snap.role === 'monitoring') {
    add(chips, 'Grafana', snap.service_active)
  } else if (snap.role === 'redis') {
    add(chips, 'Redis', snap.service_active)
  } else if (snap.role === 'pbx' || snap.role === 'sip') {
    add(chips, 'Docker', snap.docker_active)
    add(chips, 'Signal', snap.service_active)
  } else if (snap.role === 'mysql' || snap.role === 'postgres') {
    add(chips, 'Database', snap.service_active)
  } else {
    add(chips, 'Service', snap.service_active)
    add(chips, 'Nginx', snap.nginx_active)
    add(chips, 'Docker', snap.docker_active)
  }
  return chips
}

function fromEmail(snap: EmailSshSnapshot): Chip[] {
  const chips: Chip[] = []
  add(chips, 'Postfix', snap.postfix_active)
  add(chips, 'Dovecot', snap.dovecot_active)
  add(chips, 'OpenDKIM', snap.opendkim_active)
  add(chips, 'Amavis', snap.amavis_active)
  add(chips, 'ClamAV', snap.clamav_active)
  return chips
}

function fromVoice(snap: VoiceMgSnapshot): Chip[] {
  const chips: Chip[] = []
  add(chips, 'App', snap.service_active)
  add(chips, 'Docker', snap.docker_active)
  add(chips, 'Nginx', snap.nginx_active)
  return chips
}

function fromBackup(snap: BackupVaultSnapshot): Chip[] {
  const chips: Chip[] = []
  add(chips, 'Service', snap.service_active)
  add(chips, 'Docker', snap.docker_active)
  add(chips, 'Nginx', snap.nginx_active)
  return chips
}

type Props = {
  server: Server
  dockerActive?: boolean | null
}

export function HostServices({ server, dockerActive }: Props) {
  const [chips, setChips] = useState<Chip[]>([])

  useEffect(() => {
    let cancel = false
    const project = (server.project ?? '').toLowerCase()
    const kind = (server.server_type ?? '').toLowerCase()

    async function load() {
      let next: Chip[] = []
      try {
        if (project === 'infrastructure' || project === 'infra') {
          const overview = await fetchInfrastructureOverview()
          const snap = overview.servers.find((row) => row.server_id === server.id)?.snapshot
          if (snap) next = fromInfrastructure(snap)
        } else if (project === 'email') {
          const overview = await fetchEmailSshOverview()
          const snap = overview.servers.find((row) => row.server_id === server.id)?.snapshot
          if (snap) next = fromEmail(snap)
        } else if (project === 'voicemg') {
          const overview = await fetchVoiceMgOverview()
          const snap = overview.servers.find((row) => row.server_id === server.id)?.snapshot
          if (snap) next = fromVoice(snap)
        } else if (project === 'backupvault') {
          const overview = await fetchBackupVaultOverview()
          const snap = overview.servers.find((row) => row.server_id === server.id)?.snapshot
          if (snap) next = fromBackup(snap)
        } else if (project === 'ai' || kind === 'gpu') {
          const chips: Chip[] = []
          add(chips, 'Docker', dockerActive)
          next = chips
        }
      } catch {
        next = []
      }
      if (!cancel) setChips(next)
    }

    void load()
    return () => {
      cancel = true
    }
  }, [server.id, server.project, server.server_type, dockerActive])

  if (!chips.length) return null

  return (
    <div className="host-services">
      {chips.map((chip) => (
        <span key={chip.label} className={`bv-chip ${chip.up ? 'bv-chip--ok' : 'bv-chip--fail'}`}>
          {chip.label} {chip.up ? 'up' : 'down'}
        </span>
      ))}
    </div>
  )
}
