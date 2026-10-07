import { Link } from 'react-router-dom'
import { useApi } from '../lib/hooks'
import { ago } from '../lib/format'

const TONE: Record<string, string> = { INFO: 'var(--cyan)', VIGILANCE: 'var(--yellow)', CRITICAL: 'var(--red)' }
/** Ticker of ACTIVE alerts only (renders nothing when there is none). Static strip, no scrolling loop. */
export default function AlertTicker() {
  const { data } = useApi<any[]>('/api/alerts/active', { refetch: 60_000 })
  if (!data || data.length === 0) return null
  return (
    <div className="flex items-center gap-4 px-3 py-1 border-b border-line overflow-x-auto whitespace-nowrap" role="status" aria-live="polite" style={{ background: 'color-mix(in srgb, var(--bg-panel) 90%, #000)' }}>
      <span className="label shrink-0">Active alerts</span>
      {data.slice(0, 6).map((a) => (
        <Link key={a.id} to="/alerts" className="flex items-center gap-2 text-[12px]" style={{ color: 'var(--text)', textDecoration: 'none' }}>
          <span className="chip" style={{ color: TONE[a.level], borderColor: TONE[a.level] }}>{a.level}</span>
          <span className="mono">{a.title}</span><span className="text-dim mono">{ago(a.created)}</span>
        </Link>
      ))}
    </div>
  )
}
