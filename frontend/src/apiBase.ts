/** All backend routes live under /api so nginx never serves them as static files. */
export const API_BASE = '/api'

export function apiPath(path: string): string {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}
