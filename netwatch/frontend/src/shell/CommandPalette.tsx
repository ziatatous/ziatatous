import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUI } from '../lib/store'
import { useApi, useDebounced } from '../lib/hooks'
import { get, post } from '../lib/api'
import { countryName, flag, langName } from '../lib/format'
import { UI_LANGS } from '../i18n'

type Item = { id: string; label: string; hint: string; run: () => void }
const MODULES: [string, string][] = [['/', 'Briefing'], ['/topics', 'Topics'], ['/sources', 'Sources'], ['/world', 'World'], ['/corpos', 'Corpos'], ['/vitals', 'Vitals'], ['/power', 'Power network'], ['/official', 'Official'], ['/alerts', 'Alerts'], ['/agenda', 'Agenda'], ['/watch', 'Watch & timelines'], ['/search', 'Search'], ['/languages', 'Languages'], ['/system', 'System'], ['/design', 'Design system']]

export default function CommandPalette() {
  const { paletteOpen, set, calm, scanlines, sound, uiLang } = useUI()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [i, setI] = useState(0)
  const ref = useRef<HTMLInputElement>(null)
  const dq = useDebounced(q, 200)
  const countries = useApi<any[]>(paletteOpen ? '/api/world/countries' : null)
  const companies = useApi<any[]>(paletteOpen ? '/api/companies' : null)
  const sources = useApi<any[]>(paletteOpen ? '/api/sources' : null)
  const [nodes, setNodes] = useState<any[]>([])
  const close = () => set({ paletteOpen: false })

  useEffect(() => { if (paletteOpen) { setQ(''); setI(0); setTimeout(() => ref.current?.focus(), 10) } }, [paletteOpen])
  useEffect(() => { if (paletteOpen && dq.length > 1) get(`/api/graph/search?q=${encodeURIComponent(dq)}&limit=6`).then(setNodes).catch(() => setNodes([])); else setNodes([]) }, [dq, paletteOpen])

  const items = useMemo<Item[]>(() => {
    const go = (to: string) => () => { nav(to); close() }
    const all: Item[] = [
      ...MODULES.map(([to, l]) => ({ id: 'm' + to, label: l, hint: 'go to module', run: go(to) })),
      ...(countries.data || []).map((c: any) => ({ id: 'c' + c.code, label: `${flag(c.code)} ${countryName(c.code)}`, hint: 'country dossier', run: go('/world/' + c.code) })),
      { id: 'c-eu', label: '🇪🇺 European Union', hint: 'dossier', run: go('/world/EU') },
      ...(companies.data || []).map((c: any) => ({ id: 'co' + c.id, label: c.name, hint: `company · ${c.sector}`, run: go('/corpos/' + c.id) })),
      ...(sources.data || []).map((s: any) => ({ id: 's' + s.id, label: s.name, hint: `source · ${s.country}`, run: () => { set({ sourcePanel: s.id, paletteOpen: false }) } })),
      ...nodes.map((n: any) => ({ id: 'n' + n.id, label: n.label, hint: `network · ${n.type}`, run: go('/power?node=' + encodeURIComponent(n.id)) })),
      ...UI_LANGS.map((l) => ({ id: 'l' + l.code, label: `Interface: ${l.label}`, hint: 'language', run: () => { set({ uiLang: l.code }); close() } })),
      ...['fr', 'es', 'de', 'it', 'pt', 'ar', 'ru', 'zh', 'ja', 'tr', 'fa', 'hi', 'uk'].map((l) => ({ id: 'ql' + l, label: `Articles in ${langName(l)}`, hint: 'language filter', run: go('/search?lang=' + l) })),
      { id: 'a-read', label: 'Mark briefing as read', hint: 'action', run: () => { post('/api/briefing/mark-read').then(() => window.location.reload()); close() } },
      { id: 'a-collect', label: 'Collect all sources now', hint: 'action', run: () => { post('/api/system/collect'); close() } },
      { id: 'a-calm', label: `Calm mode: ${calm ? 'off' : 'on'}`, hint: 'action', run: () => { set({ calm: !calm }); close() } },
      { id: 'a-scan', label: `Scanlines: ${scanlines ? 'off' : 'on'}`, hint: 'action', run: () => { set({ scanlines: !scanlines }); close() } },
      { id: 'a-sound', label: `Alert sounds: ${sound ? 'off' : 'on'}`, hint: 'action', run: () => { set({ sound: !sound }); close() } },
    ]
    const s = q.trim().toLowerCase()
    const matched = s ? all.filter((x) => x.label.toLowerCase().includes(s) || x.hint.includes(s)) : all.filter((x) => x.id.startsWith('m') || x.id.startsWith('a-'))
    const extra: Item[] = s ? [{ id: 'q', label: `Search articles for “${q}”`, hint: 'full text', run: go('/search?q=' + encodeURIComponent(q)) }, { id: 'tl', label: `Timeline of “${q}”`, hint: 'chronology', run: go('/watch?topic=' + encodeURIComponent(q)) }] : []
    return [...matched.slice(0, 40), ...extra]
  }, [q, countries.data, companies.data, sources.data, nodes, calm, scanlines, sound, uiLang]) // eslint-disable-line

  if (!paletteOpen) return null
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setI((x) => Math.min(items.length - 1, x + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setI((x) => Math.max(0, x - 1)) }
    else if (e.key === 'Enter') { items[i]?.run() }
    else if (e.key === 'Escape') close()
  }
  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center pt-[12vh] p-4" style={{ background: 'rgba(0,0,0,.6)' }} onClick={close}>
      <div className="bevel t-yellow glow w-full max-w-[640px]" onClick={(e) => e.stopPropagation()}>
        <div className="bevel-in">
          <input ref={ref} value={q} onChange={(e) => { setQ(e.target.value); setI(0) }} onKeyDown={onKey} placeholder="Go to a country, company, person, source, topic, language or action…" aria-label="Command palette" className="w-full !border-0 !border-b !border-line text-[15px] py-3 px-4" />
          <ul className="max-h-[52vh] overflow-auto m-0 p-0 list-none" role="listbox">
            {items.map((it, k) => (
              <li key={it.id} role="option" aria-selected={k === i} onMouseEnter={() => setI(k)} onClick={it.run} className="flex justify-between gap-3 px-4 py-[6px] cursor-pointer" style={{ background: k === i ? 'color-mix(in srgb, var(--yellow) 10%, transparent)' : 'transparent', borderLeft: `2px solid ${k === i ? 'var(--yellow)' : 'transparent'}` }}>
                <span>{it.label}</span><span className="mono text-xs text-dim">{it.hint}</span>
              </li>
            ))}
            {items.length === 0 && <li className="px-4 py-3 text-dim">No match</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}
