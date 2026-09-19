import { useEffect } from 'react'

/** Live MariaDB extras poll. Not SSH collect. */
export const LIVE_EXTRAS_INTERVAL_MS = 5000

export function useLivePoll(
  tick: () => Promise<void>,
  enabled: boolean,
  intervalMs: number = LIVE_EXTRAS_INTERVAL_MS,
): void {
  useEffect(() => {
    if (!enabled) return
    let inFlight = false
    const run = async () => {
      if (inFlight || document.hidden) return
      inFlight = true
      try {
        await tick()
      } finally {
        inFlight = false
      }
    }
    const id = window.setInterval(() => {
      void run()
    }, intervalMs)
    const onVis = () => {
      if (!document.hidden) void run()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [tick, enabled, intervalMs])
}
