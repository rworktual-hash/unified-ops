import type { ServerMetric } from '../types'

export function healthScoreFromHost(host: ServerMetric | undefined): number | null {
  if (!host || host.collect_error) return null
  let score = 100
  const mem = host.mem_used_pct
  const disk = host.disk_root_pct
  const load = host.load_1m

  if (mem != null) {
    if (mem >= 92) score -= 35
    else if (mem >= 85) score -= 18
    else if (mem >= 70) score -= 6
  }
  if (disk != null) {
    if (disk >= 92) score -= 35
    else if (disk >= 85) score -= 18
    else if (disk >= 70) score -= 6
  }
  if (load != null) {
    if (load >= 8) score -= 15
    else if (load >= 4) score -= 8
  }
  return Math.max(0, Math.min(100, Math.round(score)))
}

export function healthLabel(score: number | null): 'healthy' | 'fair' | 'critical' | 'unknown' {
  if (score == null) return 'unknown'
  if (score >= 85) return 'healthy'
  if (score >= 65) return 'fair'
  return 'critical'
}
