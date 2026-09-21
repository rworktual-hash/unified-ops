const ACTION_TITLES: Record<string, string> = {
  recollect_metrics: 'Recollect metrics',
  ssh_verify: 'SSH verify',
  systemctl_restart: 'Restart service',
  investigate: 'Investigate',
  execute: 'Approved run',
}

export function actionTitle(key: string | null | undefined): string {
  if (!key) return 'Action'
  return ACTION_TITLES[key] || key.replace(/_/g, ' ')
}

export function alertTitle(type: string | null | undefined, fallback: string): string {
  if (!type || type === 'manual') return 'Requested by you'
  if (ACTION_TITLES[type]) return ACTION_TITLES[type]
  return type.replace(/_/g, ' ')
}

export function statusTitle(status: string): string {
  if (status === 'pending') return 'Pending'
  if (status === 'executed') return 'Done'
  if (status === 'rejected') return 'Rejected'
  if (status === 'failed') return 'Failed'
  return status
}
