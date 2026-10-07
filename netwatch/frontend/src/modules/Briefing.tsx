import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useApi, useChanged } from '../lib/hooks'
import { post } from '../lib/api'
import { ago, countryName, flag, langName, num, pct } from '../lib/format'
import { Bar, Chip, CountryBadge, Empty, Err, LangBadge, Panel, Sparkline, Spinner, StatTile } from '../design-system'
import { useUI } from '../lib/store'

export function TopicCard({ c }: { c: any }) {
  const span = c.first_seen && c.last_seen ? Math.max(1, (new Date(c.last_seen).getTime() - new Date(c.first_seen).getTime()) / 3600000) : 0
  return (
    <Link to={`/topics/${c.id}`} className="block py-2 border-b border-line" style={{ color: 'var(--text)', textDecoration: 'none' }}>
      <div className="font-semibold text-[15px]">{c.title}</div>
      <div className="flex gap-1 flex-wrap items-center mt-1">
        <Chip tone="cyan" title="sources × (1+ln countries) × (1+ln languages)">cov {c.score}</Chip>
        <Chip>{c.n_sources} sources</Chip><Chip>{c.n_countries} countries</Chip><Chip>{c.n_langs} languages</Chip>
        {c.langs.slice(0, 8).map((l: string) => <LangBadge key={l} lang={l} />)}
        <span className="mono text-[11px] text-dim">{c.countries.slice(0, 12).map(flag).join(' ')}</span>
        <span className="mono text-[11px] text-dim">first {ago(c.first_seen)} · last {ago(c.last_seen)}{span > 1 ? ` · span ${span.toFixed(0)}h` : ''}</span>
      </div>
    </Link>
  )
}

export default function Briefing() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const lang = useUI((s) => s.uiLang)
  const { data, error, isLoading } = useApi<any>('/api/briefing', { refetch: 120_000 })
  const changed = useChanged(data?.counters?.total)
  if (isLoading) return <Spinner />
  if (error) return <Err error={error} />
  const d = data
  const maxC = Math.max(1, ...d.counters.by_country.map((x: any) => x.n)), maxL = Math.max(1, ...d.counters.by_lang.map((x: any) => x.n))
  const markRead = async () => { await post('/api/briefing/mark-read'); qc.invalidateQueries() }
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h1 className="hud text-2xl m-0">{t('nav.briefing', 'Briefing')}</h1>
        <div className="flex items-center gap-2"><span className="mono text-xs text-dim">since {d.last_visit ? ago(d.last_visit) : 'forever (first visit)'}</span><button className="btn" onClick={markRead}>{t('common.markRead', 'Mark as read')}</button></div>
      </div>

      <Panel title="Vital signs" tone="cyan" actions={<Link to="/vitals" className="mono text-xs">all →</Link>}>
        {d.vitals.length === 0 ? <Empty>No market data collected yet (System → collectors → quotes).</Empty> :
          <div className="flex gap-5 overflow-x-auto pb-1">{d.vitals.map((v: any) => (
            <a key={v.series} href={v.source_url} target="_blank" rel="noreferrer" title={`${v.source} · ${v.ts}`} style={{ textDecoration: 'none', color: 'inherit' }} className="shrink-0">
              <div className="label">{v.label}</div>
              <div className="big text-lg">{num(v.value)}</div>
              <div className="mono text-xs" style={{ color: (v.change_pct ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>{pct(v.change_pct)}</div>
            </a>))}</div>}
      </Panel>

      <div className="grid lg:grid-cols-3 gap-3">
        <Panel title={t('briefing.since', 'Since your last visit')} className="lg:col-span-1">
          <div className="grid grid-cols-3 gap-3 mb-3">
            <StatTile label="articles" value={num(d.counters.total, 0)} changed={changed} />
            <StatTile label="official" value={num(d.counters.official, 0)} tone="yellow" />
            <StatTile label="alerts" value={num(d.counters.alerts, 0)} tone={d.counters.alerts ? 'red' : 'green'} />
          </div>
          <div className="label mb-1">by zone</div>
          <div className="grid gap-[3px] mb-3">{d.counters.by_country.map((x: any) => <Link key={x.v} to={`/world/${x.v}`} className="grid grid-cols-[120px_1fr_36px] gap-2 items-center text-xs" style={{ color: 'var(--text)', textDecoration: 'none' }}><span>{flag(x.v)} {countryName(x.v, lang)}</span><Bar value={x.n} max={maxC} /><span className="mono text-right">{x.n}</span></Link>)}</div>
          <div className="label mb-1">by language</div>
          <div className="grid gap-[3px]">{d.counters.by_lang.map((x: any) => <Link key={x.v} to={`/search?lang=${x.v}`} className="grid grid-cols-[120px_1fr_36px] gap-2 items-center text-xs" style={{ color: 'var(--text)', textDecoration: 'none' }}><span>{langName(x.v, lang)}</span><Bar value={x.n} max={maxL} tone="magenta" /><span className="mono text-right">{x.n}</span></Link>)}</div>
        </Panel>

        <Panel title={t('briefing.topics', 'Topics of the day')} className="lg:col-span-2" actions={<Link to="/topics" className="mono text-xs">all →</Link>}>
          {d.topics.length === 0 ? <Empty>No clustered topic yet — collection runs in the background (System → collect now).</Empty> : d.topics.map((c: any) => <TopicCard key={c.id} c={c} />)}
          <div className="text-dim text-xs mt-2">Ranked by breadth of coverage (sources × country diversity × language diversity), not by popularity.</div>
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-3">
        <Panel title={t('briefing.weak', 'Weak signals')} tone="yellow">
          {d.weak_signals.length === 0 ? <Empty>No weak signal detected.</Empty> : d.weak_signals.map((w: any) => (
            <div key={w.cluster_id} className="border-b border-line py-2">
              <Chip tone="yellow">{w.kind === 'growth' ? 'fast growth, few sources' : 'covered in one region only'}</Chip>{' '}
              <span className="mono text-xs text-dim">{w.kind === 'growth' ? `${w.detail.recent_6h} articles in 6h vs ${w.detail.previous_6h} before · ${w.detail.sources} sources` : `${w.detail.sources} sources, all in ${w.detail.continent}`}</span>
              <TopicCard c={w.cluster} />
            </div>))}
        </Panel>
        <Panel title={t('briefing.decided', 'What was actually decided')} actions={<Link to="/official" className="mono text-xs">all →</Link>}>
          {d.official.length === 0 ? <Empty>No official text collected yet.</Empty> : d.official.map((o: any) => (
            <div key={o.id} className="py-[6px] border-b border-line text-sm"><div className="flex gap-1 items-center"><Chip tone="cyan">{o.origin}</Chip>{o.themes.map((th: string) => <Chip key={th} tone="yellow">{th}</Chip>)}<span className="mono text-[11px] text-dim">{ago(o.ts)}</span></div><a href={o.url} target="_blank" rel="noreferrer">{o.title}</a></div>))}
        </Panel>
      </div>
      <Panel title={t('briefing.agenda', 'Next 72 hours')} actions={<Link to="/agenda" className="mono text-xs">agenda →</Link>}>
        {d.agenda.length === 0 ? <Empty>Nothing scheduled in the next 72 h.</Empty> : <div className="grid md:grid-cols-2 gap-x-6">{d.agenda.map((e: any) => <div key={e.id} className="text-sm py-1 border-b border-line flex gap-2"><span className="mono text-cyan">{e.date}</span><Chip>{e.kind}</Chip><a href={e.url} target="_blank" rel="noreferrer">{e.title}</a></div>)}</div>}
      </Panel>
    </div>
  )
}
