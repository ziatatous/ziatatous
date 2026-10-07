import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Globe from 'globe.gl'
import { geoNaturalEarth1, geoPath } from 'd3'
import { feature } from 'topojson-client'
// @ts-ignore - JSON import from world-atlas
import world110 from 'world-atlas/countries-110m.json'
import { useApi } from '../lib/hooks'
import { useUI } from '../lib/store'
import { ago, countryName, flag, hhmm, num } from '../lib/format'
import { Chip, Empty, Err, Panel, Spinner, Tabs } from '../design-system'
import ArticleRow from '../shell/ArticleRow'

// colour = event type (documented in the legend below the map)
const KIND_COL: Record<string, string> = { conflict: '#ff003c', tension: '#ff003c99', protest: '#fcee0a', quake: '#00f0ff', disaster: '#00f0ff', sanction: '#ff2a6d', diplomacy: '#8a8aa0' }
const NAME_ALIAS: Record<string, string> = { 'United States of America': 'US', Russia: 'RU', Czechia: 'CZ', 'South Korea': 'KR', 'North Korea': 'KP', 'Dem. Rep. Congo': 'CD', Congo: 'CG', "Côte d'Ivoire": 'CI', 'Bosnia and Herz.': 'BA', 'Central African Rep.': 'CF', 'S. Sudan': 'SS', 'Dominican Rep.': 'DO', 'North Macedonia': 'MK', Macedonia: 'MK', 'United Kingdom': 'GB', Palestine: 'PS', 'W. Sahara': 'MA', Myanmar: 'MM', Laos: 'LA', Vietnam: 'VN', Syria: 'SY', Iran: 'IR', Taiwan: 'TW', Moldova: 'MD', Tanzania: 'TZ', Brunei: 'BN', 'Timor-Leste': 'TL', Kosovo: 'XK' }
const WIN: Record<string, number> = { '24h': 1, '7d': 7, '30d': 30 }

function useCountryIndex(countries?: any[]) {
  return useMemo(() => { const m: Record<string, string> = {}; (countries || []).forEach((c) => { m[c.name] = c.code }); return { ...m, ...NAME_ALIAS } as Record<string, string> }, [countries])
}
function heatOf(events: any[]) {
  const m: Record<string, { country: string; v: number; kinds: Record<string, number> }> = {}
  events.forEach((e) => { if (!e.country) return; const w = Math.log1p(e.magnitude || 1); const x = (m[e.country] ||= { country: e.country, v: 0, kinds: {} }); x.v += w; x.kinds[e.kind] = (x.kinds[e.kind] || 0) + w })
  return Object.values(m).map((x) => ({ ...x, kind: Object.entries(x.kinds).sort((a, b) => b[1] - a[1])[0][0] }))
}

function GlobeView({ events, arcs, polys, countries, onPick, cursor, focus }: any) {
  const el = useRef<HTMLDivElement>(null)
  const g = useRef<any>(null)
  const heat = useMemo(() => heatOf(events), [events])
  const byCode = useMemo(() => Object.fromEntries((countries || []).map((c: any) => [c.code, c])), [countries])
  useEffect(() => {
    if (!el.current) return
    const globe: any = new (Globe as any)(el.current)
    globe.backgroundColor('rgba(0,0,0,0)').globeImageUrl('').showAtmosphere(true).atmosphereColor('#00f0ff').atmosphereAltitude(0.12)
      .polygonCapColor(() => 'rgba(30,30,44,.95)').polygonSideColor(() => 'rgba(42,42,58,.4)').polygonStrokeColor(() => '#4a4a66').polygonAltitude(0.004)
      .polygonLabel((d: any) => `<div class="mono" style="background:#12121a;border:1px solid #2a2a3a;padding:4px 8px">${d.properties.name}</div>`)
      .pointAltitude((d: any) => Math.min(0.25, 0.01 + (d.magnitude || 1) * 0.012)).pointRadius((d: any) => 0.18 + Math.min(0.6, (d.magnitude || 1) * 0.04))
      .pointColor((d: any) => KIND_COL[d.kind] || '#8a8aa0').pointLabel((d: any) => `<div class="mono" style="background:#12121a;border:1px solid #2a2a3a;padding:4px 8px;max-width:260px"><b>${d.kind}</b> ${d.magnitude ?? ''}<br/>${d.title}<br/><span style="color:#8a8aa0">${d.source} · ${d.ts}</span></div>`)
      .onPointClick((d: any) => d.url && window.open(d.url, '_blank'))
      .ringColor((d: any) => () => KIND_COL[d.kind] || '#8a8aa0').ringMaxRadius((d: any) => 2 + Math.min(7, d.v)).ringPropagationSpeed(1.2).ringRepeatPeriod(2200)
      .arcColor(() => ['#ff2a6d', '#00f0ff']).arcStroke(0.4).arcDashLength(0.4).arcDashGap(0.2).arcDashAnimateTime(3500)
      .arcLabel((d: any) => `<div class="mono" style="background:#12121a;border:1px solid #2a2a3a;padding:4px 8px;max-width:280px">${d.title}<br/><span style="color:#8a8aa0">${d.origin}</span></div>`)
      .onArcClick((d: any) => d.url && window.open(d.url, '_blank'))
    globe.controls().autoRotate = false
    globe.pointOfView({ lat: 35, lng: 15, altitude: 2.3 })
    g.current = globe
    const resize = () => { if (el.current) globe.width(el.current.clientWidth).height(el.current.clientHeight) }
    resize()
    const ro = new ResizeObserver(resize); ro.observe(el.current)
    return () => { ro.disconnect(); try { globe._destructor() } catch { /* ignore */ } }
  }, [])
  useEffect(() => { const gl = g.current; const c = focus && byCode[focus]; if (gl && c) gl.pointOfView({ lat: c.lat, lng: c.lon, altitude: 1.6 }, 900) }, [focus, byCode])
  useEffect(() => { const gl = g.current; if (!gl) return; gl.polygonsData(polys).onPolygonClick((p: any) => onPick(p.properties.name)) }, [polys, onPick])
  useEffect(() => {
    const gl = g.current; if (!gl) return
    gl.pointsData(events.filter((e: any) => e.source !== 'GDELT').map((e: any) => ({ ...e, lat: e.lat, lng: e.lon })))
    gl.ringsData(heat.slice(0, 40).map((h) => ({ ...h, lat: byCode[h.country]?.lat, lng: byCode[h.country]?.lon })).filter((h) => h.lat !== undefined))
    gl.arcsData(arcs.map((a: any) => ({ startLat: a.slat, startLng: a.slon, endLat: a.elat, endLng: a.elon, ...a })))
  }, [events, heat, arcs, byCode, cursor])
  return <div style={{ height: 520, width: '100%', overflow: 'hidden', position: 'relative' }}><div ref={el} style={{ position: 'absolute', inset: 0 }} aria-label="3D globe" /></div>
}

function FlatMap({ events, polys, onPick, countries }: any) {
  const W = 960, H = 500
  const proj = useMemo(() => geoNaturalEarth1().fitSize([W, H], { type: 'FeatureCollection', features: polys } as any), [polys])
  const path = useMemo(() => geoPath(proj), [proj])
  const heat = useMemo(() => heatOf(events), [events])
  const byCode = useMemo(() => Object.fromEntries((countries || []).map((c: any) => [c.code, c])), [countries])
  const max = Math.max(1, ...heat.map((h) => h.v))
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="2D map">
      {polys.map((p: any, i: number) => <path key={i} d={path(p) || ''} fill="#12121a" stroke="#2a2a3a" strokeWidth={0.5} onClick={() => onPick(p.properties.name)} style={{ cursor: 'pointer' }}><title>{p.properties.name}</title></path>)}
      {heat.map((h) => { const c = byCode[h.country]; if (!c) return null; const [x, y] = proj([c.lon, c.lat]) || [0, 0]; return <circle key={h.country} cx={x} cy={y} r={3 + 16 * (h.v / max)} fill={KIND_COL[h.kind]} fillOpacity={0.35} stroke={KIND_COL[h.kind]}><title>{`${countryName(h.country)} — ${h.kind} (${h.v.toFixed(1)})`}</title></circle> })}
      {events.filter((e: any) => e.source !== 'GDELT').map((e: any) => { const [x, y] = proj([e.lon, e.lat]) || [0, 0]; return <circle key={e.id} cx={x} cy={y} r={1.5 + Math.min(5, (e.magnitude || 1) * 0.5)} fill={KIND_COL[e.kind]}><title>{`${e.title} (${e.source})`}</title></circle> })}
    </svg>)
}

function Dossier({ code }: { code: string }) {
  const lang = useUI((s) => s.uiLang)
  const { data: d, error, isLoading } = useApi<any>(`/api/world/country/${code}`)
  const [tab, setTab] = useState('news')
  if (isLoading) return <Spinner />
  if (error) return <Err error={error} />
  const c = d.country
  return (
    <Panel title={<>{flag(code)} {c.name === 'European Union' ? 'European Union' : countryName(code, lang)}</>} tone="yellow" actions={d.press_freedom_rank ? <Chip tone="cyan" title="RSF World Press Freedom Index rank">RSF #{d.press_freedom_rank}</Chip> : undefined}>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'news', label: 'News' }, { id: 'events', label: `Events ${d.events.length}` }, { id: 'official', label: `Official ${d.official.length}` }, { id: 'econ', label: 'Economy' }, { id: 'corp', label: `Companies ${d.companies.length}` }, { id: 'people', label: 'Leaders' }, { id: 'agenda', label: 'Agenda' }]} />
      <div className="mt-2 max-h-[560px] overflow-y-auto pr-1">
        {tab === 'news' && <div className="grid md:grid-cols-2 gap-4">
          <div><div className="label">Local sources ({d.local_sources.length} registered)</div>{d.local_news.length ? d.local_news.map((a: any) => <ArticleRow key={a.id} a={a} />) : <Empty>no local article</Empty>}</div>
          <div><div className="label">Foreign sources writing about it</div>{d.foreign_news.length ? d.foreign_news.map((a: any) => <ArticleRow key={a.id} a={a} />) : <Empty>no foreign article</Empty>}</div></div>}
        {tab === 'events' && (d.events.length ? d.events.map((e: any, i: number) => <div key={i} className="py-1 border-b border-line text-sm flex gap-2 flex-wrap"><Chip tone={e.kind === 'conflict' ? 'red' : e.kind === 'protest' ? 'yellow' : 'cyan'}>{e.kind}</Chip><span className="mono text-xs text-dim">{hhmm(e.ts)}</span>{e.url ? <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a> : e.title}<span className="text-dim text-xs">{e.source}{e.magnitude ? ` · ${num(e.magnitude)}` : ''}</span></div>) : <Empty>No event in the last 30 days.</Empty>)}
        {tab === 'official' && (d.official.length ? d.official.map((o: any) => <div key={o.id} className="py-1 border-b border-line text-sm"><Chip tone="cyan">{o.origin}</Chip> <a href={o.url} target="_blank" rel="noreferrer">{o.title}</a> <span className="mono text-[11px] text-dim">{o.ts?.slice(0, 10)}</span></div>) : <Empty>No official text found.</Empty>)}
        {tab === 'econ' && (d.indicators.length ? <table className="data"><tbody>{d.indicators.map((i: any) => <tr key={i.series}><td>{i.label}</td><td className="mono">{num(i.value)} {i.unit}</td><td className="mono text-xs text-dim">{i.ts?.slice(0, 4)}</td><td><a href={i.source_url} target="_blank" rel="noreferrer" className="text-xs">{i.source} ↗</a></td></tr>)}</tbody></table> : <Empty>No indicator for this country (World Bank loads FR, ES, DE, IT, US, CN, GB, JP, BR, IN; euro-area series are in Vitals).</Empty>)}
        {tab === 'corp' && (d.companies.length ? d.companies.map((x: any) => <div key={x.id} className="py-1 border-b border-line"><Link to={`/corpos/${x.id}`}>{x.name}</Link> <Chip>{x.sector}</Chip></div>) : <Empty>No tracked company based here.</Empty>)}
        {tab === 'people' && (d.leaders?.length ? d.leaders.map((l: any, i: number) => <div key={i} className="py-1 border-b border-line text-sm"><Chip tone="magenta">{l.role}</Chip> <a href={l.url} target="_blank" rel="noreferrer">{l.name}</a></div>) : <Empty>No leader loaded yet (collector “wikidata_leaders”).</Empty>)}
        {tab === 'agenda' && (d.agenda.length ? d.agenda.map((e: any, i: number) => <div key={i} className="py-1 border-b border-line text-sm"><span className="mono text-cyan">{e.date}</span> <Chip>{e.kind}</Chip> <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a></div>) : <Empty>Nothing scheduled (elections, summits…).</Empty>)}
      </div>
    </Panel>
  )
}

export default function World() {
  const { code } = useParams()
  const nav = useNavigate()
  const [win, setWin] = useState('7d')
  const [mode, setMode] = useState<'3d' | '2d'>('3d')
  const [kinds, setKinds] = useState<Record<string, boolean>>({})
  const countries = useApi<any[]>('/api/world/countries')
  const events = useApi<any[]>(`/api/world/events?days=${WIN[win]}&limit=20000`, { refetch: 300_000 })
  const arcs = useApi<any[]>('/api/world/arcs?days=1')
  const idx = useCountryIndex(countries.data)
  const polys = useMemo(() => (feature(world110 as any, (world110 as any).objects.countries) as any).features, [])
  const [play, setPlay] = useState(false)
  const [cursor, setCursor] = useState<number | null>(null) // epoch ms, null = live (everything)
  const range = useMemo(() => { const now = Date.now(); return [now - WIN[win] * 86400000, now] }, [win, events.data])
  useEffect(() => { setCursor(null); setPlay(false) }, [win])
  useEffect(() => {
    if (!play) return
    const step = (range[1] - range[0]) / 120
    const id = setInterval(() => setCursor((c) => { const n = (c ?? range[0]) + step; if (n >= range[1]) { setPlay(false); return null } return n }), 150)
    return () => clearInterval(id)
  }, [play, range])
  const kindList = useMemo(() => [...new Set((events.data || []).map((e) => e.kind))], [events.data])
  const shown = useMemo(() => (events.data || []).filter((e) => kinds[e.kind] !== false && (cursor === null || (new Date(e.ts).getTime() <= cursor && new Date(e.ts).getTime() > cursor - 86400000 * Math.max(1, WIN[win] / 7)))), [events.data, kinds, cursor, win])
  const pick = (name: string) => { const cc = idx[name]; if (cc) nav('/world/' + cc) }
  const tree = useMemo(() => { const t: Record<string, Record<string, any[]>> = {}; (countries.data || []).forEach((c) => { ((t[c.continent] ||= {})[c.region] ||= []).push(c) }); return t }, [countries.data])
  const CONT: Record<string, string> = { EU: 'Europe', AS: 'Asia', AF: 'Africa', NA: 'North America', SA: 'South America', OC: 'Oceania' }
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-2 flex-wrap"><h1 className="hud text-2xl m-0">World</h1>
        <div className="flex gap-2 flex-wrap items-center">
          {[['FR', 'France'], ['ES', 'España'], ['EU', 'EU']].map(([c, n]) => <Link key={c} to={`/world/${c}`} className={`btn ${code === c ? '' : 'ghost'}`} style={{ textDecoration: 'none' }}>{c === 'EU' ? '🇪🇺' : flag(c)} {n}</Link>)}
          <Tabs value={win} onChange={setWin} tabs={Object.keys(WIN).map((w) => ({ id: w, label: w }))} /><Tabs value={mode} onChange={setMode} tabs={[{ id: '3d', label: '3D' }, { id: '2d', label: '2D' }]} /></div></div>
      <div className="grid xl:grid-cols-[220px_minmax(0,1fr)] gap-3">
        <Panel title="Continent › region › country" className="hide-sm"><div className="max-h-[560px] overflow-y-auto text-sm">
          {Object.entries(tree).map(([ct, regs]) => <details key={ct}><summary className="cursor-pointer hud">{CONT[ct] || ct}</summary>{Object.entries(regs).map(([r, cs]) => <details key={r} className="pl-3"><summary className="cursor-pointer text-dim">{r}</summary><ul className="list-none m-0 pl-3">{cs.map((c: any) => <li key={c.code}><Link to={`/world/${c.code}`} style={{ color: code === c.code ? 'var(--yellow)' : undefined }}>{flag(c.code)} {countryName(c.code)}</Link></li>)}</ul></details>)}</details>)}</div></Panel>
        <div className="grid gap-3 min-w-0 grid-cols-[minmax(0,1fr)]">
          <Panel pad={false} title={`${shown.length} events · ${win}`} actions={<><button className="btn ghost" onClick={() => setPlay(!play)} aria-label="play timeline">{play ? '❚❚' : '▶'} replay</button>
            {cursor !== null && <span className="mono text-xs">{new Date(cursor).toLocaleDateString()}</span>}</>}>
            {events.error && <Err error={events.error} />}
            {mode === '3d' ? <GlobeView events={shown} arcs={arcs.data || []} polys={polys} countries={countries.data} onPick={pick} cursor={cursor} focus={code?.toUpperCase()} /> : <div className="p-2"><FlatMap events={shown} polys={polys} onPick={pick} countries={countries.data} /></div>}
            {(events.data || []).length === 0 && !events.isLoading && <Empty>No event collected yet (collectors: usgs, gdacs, gdelt, acled, reliefweb).</Empty>}
            <div className="px-3 pb-2 flex gap-2 flex-wrap items-center"><input type="range" min={range[0]} max={range[1]} step={600000} value={cursor ?? range[1]} onChange={(e) => { setPlay(false); setCursor(+e.target.value >= range[1] ? null : +e.target.value) }} className="flex-1 min-w-[160px]" aria-label="time cursor" />
              {kindList.map((k) => <button key={k} className="chip" onClick={() => setKinds({ ...kinds, [k]: kinds[k] === false })} style={{ borderLeft: `3px solid ${KIND_COL[k] || '#8a8aa0'}`, opacity: kinds[k] === false ? 0.4 : 1 }}>{k}</button>)}</div>
            <div className="px-3 pb-2 text-[11px] text-dim">Colour = type: red conflict/tension · yellow protest · cyan natural hazard · pink sanction. Rings = intensity per country (log-weighted GDELT/ACLED volume); dots = individual events (USGS, GDACS, ACLED); animated arcs = official documents naming two countries today.</div>
          </Panel>
          {code ? <Dossier code={code.toUpperCase()} key={code} /> : <Empty>Click a country (map, tree or ⌘K) to open its dossier.</Empty>}
        </div>
      </div>
    </div>
  )
}
