import { Link } from 'react-router-dom'
import { useApi } from '../lib/hooks'
import { ago } from '../lib/format'

const TONE: Record<string, string> = { INFO: 'var(--cyan)', VIGILANCE: 'var(--yellow)', CRITICAL: 'var(--red)' }
/** Ticker of ACTIVE alerts only (renders nothing when there is none). Static strip, no scrolling loop. */
export default function AlertTicker() {
  const { data: all } = useApi<any[]>('/api/alerts/active', { refetch: 60_000 })
  // INFO alerts live in the Alerts screen only: the strip is reserved for what needs attention now
  const data = (all || []).filter((a) => a.level !== 'INFO')
  if (data.length === 0) return null
  return (
    <div className="flex items-center gap-4 px-3 py-1 border-b border-line overflow-x-auto whitespace-nowrap" role="status" aria-live="polite" style={{ background: 'color-mix(in srgb, var(--bg-panel) 90%, #000)' }}>
      <span className="label shrink-0">Alerts</span>
      {data.slice(0, 3).map((a) => (
        <Link key={a.id} to="/alerts" className="flex items-center gap-2 text-[12px] min-w-0" style={{ color: 'var(--text)', textDecoration: 'none' }}>
          <span className="chip" style={{ color: TONE[a.level], borderColor: TONE[a.level] }}>{a.level}</span>
          <span className="mono truncate max-w-[420px]">{a.title}</span><span className="text-dim mono">{ago(a.created)}</span>
        </Link>
      ))}
    </div>
  )
}
