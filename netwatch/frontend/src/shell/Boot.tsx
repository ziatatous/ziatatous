import { useEffect, useState } from 'react'
import { get } from '../lib/api'
import { useUI } from '../lib/store'
import { ago } from '../lib/format'

type Line = { text: string; tone?: string }
/** Start-up sequence: shows the REAL system state for ~2.5 s (any key skips). Once per browser session. */
export default function Boot() {
  const calm = useUI((s) => s.calm)
  const [lines, setLines] = useState<Line[] | null>(null)
  const [done, setDone] = useState(() => { try { return sessionStorage.getItem('nw:booted') === '1' } catch { return false } })

  useEffect(() => {
    if (done) return
    get('/api/startup').then((d) => {
      const f = d.feeds || {}
      const ok = f.ok || 0, bad = (f.error || 0) + (f.dead || 0), fresh = f.new || 0
      const al = d.alerts || {}
      const L: Line[] = [
        { text: 'NETWATCH // system state' },
        { text: `sources synced: ${ok}  ·  in error: ${bad}  ·  never fetched: ${fresh}`, tone: bad ? 'var(--yellow)' : 'var(--green)' },
        { text: `new articles since last visit${d.last_visit ? ' (' + ago(d.last_visit) + ')' : ' (first visit)'}: ${d.new_articles}`, tone: 'var(--cyan)' },
        { text: `active alerts — CRITICAL ${al.CRITICAL || 0} · VIGILANCE ${al.VIGILANCE || 0} · INFO ${al.INFO || 0}`, tone: al.CRITICAL ? 'var(--red)' : al.VIGILANCE ? 'var(--yellow)' : 'var(--green)' },
        ...Object.entries(d.last_collect || {}).map(([k, v]: any) => ({ text: `last collection ${k.padEnd(8)} ${v ? ago(v) : 'never'}`, tone: v ? 'var(--text-dim)' : 'var(--yellow)' })),
        ...((d.collectors_failing || []).length ? [{ text: `failing collectors: ${d.collectors_failing.join(', ')}`, tone: 'var(--red)' }] : []),
      ]
      setLines(L)
    }).catch(() => setLines([{ text: 'backend not reachable — is NETWATCH running?', tone: 'var(--red)' }]))
  }, [done])

  const finish = () => { try { sessionStorage.setItem('nw:booted', '1') } catch { /* ignore */ } setDone(true) }
  useEffect(() => {
    if (done || !lines) return
    const t = setTimeout(finish, calm ? 800 : 2600)
    const k = () => finish()
    window.addEventListener('keydown', k); window.addEventListener('click', k)
    return () => { clearTimeout(t); window.removeEventListener('keydown', k); window.removeEventListener('click', k) }
  }, [done, lines, calm])

  if (done) return null
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6" style={{ background: 'var(--bg-void)' }}>
      <div className="mono text-[13px] w-full max-w-[720px]">
        {(lines || [{ text: 'connecting…' }]).map((l, i) => <div key={i} style={{ color: l.tone || 'var(--text)', animation: calm ? undefined : `flashin .4s ${i * 0.12}s both` }}>{i === 0 ? '▌' : '›'} {l.text}</div>)}
        <div className="text-dim mt-4 text-xs">press any key to skip</div>
      </div>
    </div>
  )
}
