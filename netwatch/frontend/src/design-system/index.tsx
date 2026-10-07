import { ReactNode, useEffect, useMemo, useRef, useState, CSSProperties } from 'react'
import * as echarts from 'echarts'
import { useUI } from '../lib/store'
import { flag, countryName, langName } from '../lib/format'

export type Tone = 'neutral' | 'cyan' | 'yellow' | 'red' | 'green' | 'magenta'
const toneVar: Record<Tone, string> = { neutral: 'var(--text-dim)', cyan: 'var(--cyan)', yellow: 'var(--yellow)', red: 'var(--red)', green: 'var(--green)', magenta: 'var(--magenta)' }
export const toneColor = (t: Tone) => toneVar[t]

/** Bevelled HUD panel. `tone` is semantic (see Legend). */
export function Panel({ title, tone = 'neutral', actions, children, className = '', pad = true, style }: { title?: ReactNode; tone?: Tone; actions?: ReactNode; children?: ReactNode; className?: string; pad?: boolean; style?: CSSProperties }) {
  return (
    <section className={`bevel ${tone !== 'neutral' ? 't-' + tone : ''} ${className}`} style={style}>
      <div className="bevel-in flex flex-col">
        {(title || actions) && (
          <header className="flex items-center justify-between gap-2 px-3 pt-2 pb-1">
            <h2 className="hud m-0 text-[13px] font-semibold tracking-[.16em]" style={{ color: tone === 'neutral' ? 'var(--text)' : toneVar[tone] }}>{title}</h2>
            <div className="flex items-center gap-2">{actions}</div>
          </header>
        )}
        <div className={pad ? 'p-3 pt-2 flex-1 min-h-0' : 'flex-1 min-h-0'}>{children}</div>
      </div>
    </section>
  )
}

export const Chip = ({ tone = 'neutral', children, title }: { tone?: Tone; children: ReactNode; title?: string }) => <span title={title} className={`chip ${tone !== 'neutral' ? tone : ''}`}>{children}</span>

export const LangBadge = ({ lang }: { lang?: string | null }) => lang ? <span className="chip cyan" title={langName(lang)}>{lang.toUpperCase()}</span> : null
export const CountryBadge = ({ cc, name }: { cc?: string | null; name?: boolean }) => cc ? <span className="chip" title={countryName(cc)}>{flag(cc)} {name ? countryName(cc) : cc}</span> : null

const OWN_TONE: Record<string, Tone> = { state: 'red', public: 'cyan', private: 'yellow', foundation: 'green', nonprofit: 'green', cooperative: 'green', independent: 'green', unknown: 'neutral' }
/** Source badge: colour = ownership type; click opens the full fiche. */
export function SourceBadge({ id, name, ownership, state }: { id: string; name?: string; ownership?: string | null; state?: number | boolean }) {
  const open = useUI((s) => s.set)
  const o = ownership || 'unknown'
  return (
    <button className={`chip ${OWN_TONE[o] || ''}`} title={`${o}${state ? ' · state-affiliated' : ''} — click for the full source fiche`} onClick={(e) => { e.stopPropagation(); open({ sourcePanel: id }) }}>
      {state ? '◆ ' : ''}{name || id}
    </button>
  )
}

export function Spinner({ label }: { label?: string }) { return <div className="mono text-dim text-xs p-3">{label ?? '…'}</div> }
export const Empty = ({ children }: { children?: ReactNode }) => <div className="text-dim text-sm p-4 text-center">{children ?? '—'}</div>
export const Err = ({ error }: { error: any }) => <div className="text-red text-sm p-3 mono">⚠ {String(error?.message || error)}</div>

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="flex gap-1 flex-wrap" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={t.id === value} onClick={() => onChange(t.id)}
          className="hud px-3 py-1 text-[12px] font-semibold border" style={{ borderColor: t.id === value ? 'var(--yellow)' : 'var(--line)', color: t.id === value ? 'var(--yellow)' : 'var(--text-dim)', background: 'transparent' }}>{t.label}</button>
      ))}
    </div>
  )
}

/** Big stat with optional delta; glitches once when the value really changes. */
export function StatTile({ label, value, delta, tone = 'cyan', sub, changed }: { label: string; value: ReactNode; delta?: number | null; tone?: Tone; sub?: ReactNode; changed?: boolean }) {
  const dt: Tone = delta === null || delta === undefined ? 'neutral' : delta > 0 ? 'green' : delta < 0 ? 'red' : 'neutral'
  return (
    <div>
      <div className="label">{label}</div>
      <div className={`big text-2xl ${changed ? 'glitch-once' : ''}`} style={{ color: toneVar[tone] }}>{value}</div>
      {delta !== null && delta !== undefined && <div className="mono text-xs" style={{ color: toneVar[dt] }}>{delta > 0 ? '▲' : delta < 0 ? '▼' : '■'} {Math.abs(delta).toFixed(2)}%</div>}
      {sub && <div className="text-dim text-xs">{sub}</div>}
    </div>
  )
}

/** Horizontal gauge: value within [min,max] (e.g. 10-year range → percentile); marker shows position. */
export function Gauge({ value, min, max, tone = 'cyan', label, thresholds }: { value: number; min: number; max: number; tone?: Tone; label?: string; thresholds?: { above?: number | null; below?: number | null } }) {
  const p = max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0.5
  const mark = (v?: number | null) => (v !== null && v !== undefined && max > min ? `${Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100))}%` : null)
  return (
    <div title={label} role="meter" aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}>
      <div className="relative h-[6px]" style={{ background: 'var(--line)' }}>
        <div className="absolute inset-y-0 left-0" style={{ width: `${p * 100}%`, background: toneVar[tone], opacity: .55 }} />
        <div className="absolute -top-[3px] w-[2px] h-[12px]" style={{ left: `${p * 100}%`, background: toneVar[tone] }} />
        {[thresholds?.above, thresholds?.below].map((t, i) => mark(t) && <div key={i} className="absolute -top-[2px] w-px h-[10px]" style={{ left: mark(t)!, background: 'var(--yellow)' }} title="alert threshold" />)}
      </div>
    </div>
  )
}

export function Sparkline({ data, tone = 'cyan', width = 120, height = 28 }: { data: number[]; tone?: Tone; width?: number; height?: number }) {
  if (data.length < 2) return <svg width={width} height={height} />
  const lo = Math.min(...data), hi = Math.max(...data), r = hi - lo || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - 2 - ((v - lo) / r) * (height - 4)}`).join(' ')
  const up = data[data.length - 1] >= data[0]
  const c = tone === 'neutral' ? (up ? 'var(--green)' : 'var(--red)') : toneVar[tone]
  return <svg width={width} height={height} aria-hidden><polyline points={pts} fill="none" stroke={c} strokeWidth={1.5} /></svg>
}

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&'
/** "Decrypt" effect: letters resolve once. Use ONLY for fresh data (fresh=true). */
export function Decrypt({ text, fresh = false }: { text: string; fresh?: boolean }) {
  const calm = useUI((s) => s.calm)
  const [out, setOut] = useState(text)
  useEffect(() => {
    if (!fresh || calm) { setOut(text); return }
    let f = 0; const total = 12
    const id = setInterval(() => {
      f++
      setOut(text.split('').map((c, i) => (c === ' ' || i < (f / total) * text.length ? c : GLYPHS[Math.floor(Math.random() * GLYPHS.length)])).join(''))
      if (f >= total) { clearInterval(id); setOut(text) }
    }, 30)
    return () => clearInterval(id)
  }, [text, fresh, calm])
  return <>{out}</>
}

/** ECharts wrapper themed with the design tokens. */
export function Chart({ option, height = 220, onClick }: { option: echarts.EChartsCoreOption; height?: number; onClick?: (p: any) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  useEffect(() => {
    if (!ref.current) return
    const c = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    chart.current = c
    const ro = new ResizeObserver(() => c.resize())
    ro.observe(ref.current)
    return () => { ro.disconnect(); c.dispose() }
  }, [])
  useEffect(() => {
    const c = chart.current; if (!c) return
    c.setOption({
      backgroundColor: 'transparent', textStyle: { fontFamily: 'JetBrains Mono', color: '#8a8aa0' }, animationDuration: 250,
      grid: { left: 44, right: 12, top: 18, bottom: 26 },
      tooltip: { trigger: 'axis', backgroundColor: '#12121a', borderColor: '#2a2a3a', textStyle: { color: '#e6e6f0', fontSize: 12 } },
      ...option,
    } as any, true)
    c.off('click'); if (onClick) c.on('click', onClick)
  }, [option, onClick])
  return <div ref={ref} style={{ height, width: '100%' }} />
}
export const axisStyle = { axisLine: { lineStyle: { color: '#2a2a3a' } }, axisLabel: { color: '#8a8aa0', fontSize: 10 }, splitLine: { lineStyle: { color: '#1b1b28' } } }

/** Colour legend: documents the semantic use of every colour. */
export function Legend() {
  const rows: [Tone, string, string][] = [
    ['yellow', 'Yellow', 'Vigilance level · interactive element · focus · action possible'],
    ['red', 'Red', 'Critical alert · strong drop · conflict · state-affiliated media'],
    ['cyan', 'Cyan', 'Data · links · neutral information · selection · INFO level'],
    ['green', 'Green', 'Normal state · rise · collection OK · independent / non-profit ownership'],
    ['magenta', 'Magenta', 'Entities, persons, power network'],
  ]
  return (
    <div className="grid gap-1 text-sm">
      {rows.map(([t, n, d]) => <div key={n} className="flex items-start gap-2"><span className="inline-block w-3 h-3 mt-1 shrink-0" style={{ background: toneVar[t] }} /><span><b className="hud" style={{ color: toneVar[t] }}>{n}</b> <span className="text-dim">— {d}</span></span></div>)}
      <div className="text-dim text-xs mt-1">Source badges: <span className="chip red">state</span> <span className="chip cyan">public</span> <span className="chip yellow">private</span> <span className="chip green">foundation / non-profit / cooperative</span> <span className="chip">unknown</span></div>
    </div>
  )
}

export function useKey(handler: (e: KeyboardEvent) => void, deps: any[] = []) {
  useEffect(() => { window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler) }, deps) // eslint-disable-line
}

export function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="grid gap-1 text-sm"><span className="label">{label}</span>{children}</label> }

export function Bar({ value, max, tone = 'cyan' }: { value: number; max: number; tone?: Tone }) {
  return <div className="h-[6px] w-full" style={{ background: 'var(--line)' }}><div className="h-full" style={{ width: `${max ? Math.min(100, (value / max) * 100) : 0}%`, background: toneVar[tone], opacity: .8 }} /></div>
}

export function useSorted<T>(rows: T[], key: keyof T | null, dir: 1 | -1 = 1) {
  return useMemo(() => (key ? [...rows].sort((a: any, b: any) => (a[key] > b[key] ? dir : -dir)) : rows), [rows, key, dir])
}
