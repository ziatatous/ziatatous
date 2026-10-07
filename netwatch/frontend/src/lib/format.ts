export function ago(iso?: string | null, lang = 'en'): string {
  if (!iso) return '—'
  const t = new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso).getTime()
  const s = Math.round((Date.now() - t) / 1000)
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: 'auto', style: 'short' })
  const a = Math.abs(s)
  if (a < 90) return rtf.format(-Math.round(s / 60) || 0, 'minute')
  if (a < 5400) return rtf.format(-Math.round(s / 60), 'minute')
  if (a < 129600) return rtf.format(-Math.round(s / 3600), 'hour')
  if (a < 86400 * 45) return rtf.format(-Math.round(s / 86400), 'day')
  return rtf.format(-Math.round(s / 86400 / 30), 'month')
}
export const hhmm = (iso?: string | null) => (iso ? new Date(iso).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')
export function num(v?: number | null, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  return v.toLocaleString(undefined, { maximumFractionDigits: a >= 1000 ? 0 : a >= 10 ? 1 : d })
}
export const pct = (v?: number | null) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)
export const bytes = (n: number) => (n > 1e9 ? (n / 1e9).toFixed(2) + ' GB' : n > 1e6 ? (n / 1e6).toFixed(1) + ' MB' : (n / 1e3).toFixed(0) + ' kB')
export function countryName(code?: string | null, lang = 'en') {
  if (!code) return '—'
  try { return new Intl.DisplayNames([lang], { type: 'region' }).of(code) || code } catch { return code }
}
export function langName(code?: string | null, lang = 'en') {
  if (!code) return '—'
  try { return new Intl.DisplayNames([lang], { type: 'language' }).of(code) || code } catch { return code }
}
export const flag = (cc?: string | null) => (cc && cc.length === 2 ? String.fromCodePoint(...[...cc.toUpperCase()].map((c) => 127397 + c.charCodeAt(0))) : '🏳')
