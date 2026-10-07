export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg) } }

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined })
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = j.detail || msg } catch { /* ignore */ }
    throw new ApiError(r.status, typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return r.json()
}
export const get = <T = any>(url: string) => req<T>('GET', url)
export const post = <T = any>(url: string, body?: unknown) => req<T>('POST', url, body ?? {})
export const put = <T = any>(url: string, body?: unknown) => req<T>('PUT', url, body ?? {})
export const del = <T = any>(url: string) => req<T>('DELETE', url)

export function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)) })
  const s = p.toString()
  return s ? `?${s}` : ''
}
