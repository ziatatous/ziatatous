import { ReactNode, useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useApi, useSSE } from '../lib/hooks'
import { useUI } from '../lib/store'
import { post } from '../lib/api'
import { Chip } from '../design-system'
import AlertTicker from './AlertTicker'
import CommandPalette from './CommandPalette'
import Help from './Help'
import SourcePanel from './SourcePanel'
import ArticleReader from './ArticleReader'
import Boot from './Boot'
import { playAlert } from '../lib/sound'

const NAV: [string, string, string][] = [
  ['/', 'briefing', '◈'], ['/topics', 'topics', '≣'], ['/sources', 'sources', '◐'], ['/world', 'world', '◍'], ['/corpos', 'corpos', '▣'],
  ['/vitals', 'vitals', '∿'], ['/power', 'power', '⌘'], ['/official', 'official', '§'], ['/alerts', 'alerts', '▲'], ['/agenda', 'agenda', '▤'],
  ['/watch', 'watch', '◉'], ['/search', 'search', '⌕'], ['/languages', 'languages', 'あ'], ['/system', 'system', '⚙'],
]
const KEYS: Record<string, string> = { b: '/', t: '/topics', s: '/sources', m: '/world', c: '/corpos', v: '/vitals', p: '/power', o: '/official', a: '/alerts', g: '/agenda', w: '/watch', f: '/search', l: '/languages', y: '/system', d: '/design' }

export default function Shell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const ui = useUI()
  const nav = useNavigate()
  const loc = useLocation()
  const qc = useQueryClient()
  const startup = useApi<any>('/api/startup', { refetch: 60_000 })
  const active = useApi<any[]>('/api/alerts/active', { refetch: 60_000 })
  const [chord, setChord] = useState(false)

  useEffect(() => { document.documentElement.dataset.calm = String(ui.calm); document.documentElement.dataset.scanlines = ui.scanlines ? 'on' : 'off' }, [ui.calm, ui.scanlines])
  useEffect(() => { document.documentElement.lang = ui.uiLang; import('../i18n').then((m) => m.default.changeLanguage(ui.uiLang)) }, [ui.uiLang])
  // expire "immersion day" the next day
  useEffect(() => { if (ui.immersionDay && ui.immersionDay !== new Date().toISOString().slice(0, 10)) ui.set({ immersionDay: null, uiLang: 'en' }) }, []) // eslint-disable-line

  const burst = useRef<ReturnType<typeof setTimeout> | null>(null)
  useSSE((e) => {
    if (e.kind === 'alert') {
      // alerts often arrive in bursts: refresh once, not once per alert
      if (burst.current) clearTimeout(burst.current)
      burst.current = setTimeout(() => { qc.invalidateQueries({ queryKey: ['/api/alerts/active'] }); qc.invalidateQueries({ queryKey: ['/api/alerts'] }) }, 1500)
      if (e.level === 'INFO') return // INFO: no sound, no desktop notification
      if (ui.sound) playAlert(e.level)
      if (ui.notify && 'Notification' in window && Notification.permission === 'granted') new Notification(`NETWATCH · ${e.level}`, { body: e.title })
    }
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target as HTMLElement)?.isContentEditable
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); ui.set({ paletteOpen: !ui.paletteOpen }); return }
      if (typing) return
      if (e.key === '?') { ui.set({ helpOpen: !ui.helpOpen }); return }
      if (e.key === 'Escape') { ui.set({ paletteOpen: false, helpOpen: false, sourcePanel: null, articleId: null }); setChord(false); return }
      if (e.key === '.') { ui.set({ calm: !ui.calm }); return }
      if (e.key === '/') { e.preventDefault(); nav('/search'); return }
      if (chord) { setChord(false); const to = KEYS[e.key.toLowerCase()]; if (to) { e.preventDefault(); nav(to) } return }
      if (e.key === 'g' && !e.ctrlKey && !e.metaKey) { setChord(true); setTimeout(() => setChord(false), 1500) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chord, ui, nav])

  const badge = (to: string): number => {
    // no "99+" on the very first visit (everything is new): the badge starts after the first "mark as read"
    if (to === '/') return startup.data?.last_visit ? startup.data?.new_articles ?? 0 : 0
    if (to === '/alerts') return (active.data || []).filter((a: any) => a.level !== 'INFO').length
    return 0
  }
  const failing = startup.data?.collectors_failing?.length ?? 0

  return (
    <div className="relative z-[1] flex h-full">
      <Boot />
      <nav className="w-[64px] md:w-[196px] shrink-0 border-r border-line flex flex-col" style={{ background: 'color-mix(in srgb, var(--bg-void) 85%, #000)' }} aria-label="Modules">
        <div className="px-3 py-3 border-b border-line">
          <div className="big text-[15px] text-yellow hide-sm-text">NET<span className="text-cyan">WATCH</span></div>
          <div className="mono text-[10px] text-dim hidden md:block">global watch terminal</div>
        </div>
        <ul className="flex-1 overflow-y-auto m-0 p-0 list-none py-2">
          {NAV.map(([to, k, ic]) => (
            <li key={to}>
              <NavLink to={to} end={to === '/'} className="flex items-center gap-3 px-4 py-[7px] hud text-[14px] font-semibold border-l-2"
                style={({ isActive }) => ({ borderColor: isActive ? 'var(--yellow)' : 'transparent', color: isActive ? 'var(--yellow)' : 'var(--text-dim)', background: isActive ? 'color-mix(in srgb, var(--yellow) 6%, transparent)' : 'transparent', textDecoration: 'none' })}>
                <span className="w-5 text-center">{ic}</span>
                <span className="hidden md:inline flex-1">{t(`nav.${k}`, k)}</span>
                {badge(to) > 0 && <span className="chip cyan" style={{ minWidth: 20, justifyContent: 'center' }}>{badge(to) > 99 ? '99+' : badge(to)}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="p-2 border-t border-line grid gap-1 text-[11px]">
          {failing > 0 && <Chip tone="red" title={startup.data.collectors_failing.join(', ')}>{failing} collector(s) failing</Chip>}
          <button className="btn ghost" onClick={() => ui.set({ calm: !ui.calm })} title="Key: .">{ui.calm ? '◼' : '◻'} <span className="hidden md:inline">{t('common.calm', 'Calm mode')}</span></button>
          <button className="btn ghost" onClick={() => ui.set({ paletteOpen: true })}><span className="hidden md:inline">⌘K</span><span className="md:hidden">⌘</span></button>
          <button className="btn ghost" onClick={() => ui.set({ helpOpen: true })}>?</button>
        </div>
      </nav>
      <div className="flex-1 min-w-0 flex flex-col">
        <AlertTicker />
        <main className="flex-1 overflow-y-auto p-3 md:p-4" id="main" key={loc.pathname.split('/')[1]}>
          {chord && <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-50 chip yellow">g → b s m c v p o a g w f l y</div>}
          {children}
        </main>
      </div>
      <SourcePanel />
      <ArticleReader />
      <CommandPalette />
      <Help />
    </div>
  )
}
