/** Show every stored timestamp in India time (IST). Naive values are UTC. */
export function formatWhen(value: string | null | undefined): string {
  if (!value) return ''
  const trimmed = value.trim()
  const hasZone = /[zZ]$|[+-]\d{2}:\d{2}$/.test(trimmed)
  const iso = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  const date = new Date(hasZone ? iso : `${iso}Z`)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
