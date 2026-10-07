import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useApi } from '../lib/hooks'
import { del, post } from '../lib/api'
import { countryName, flag, hhmm } from '../lib/format'
import { Chart, axisStyle, Chip, Empty, Panel, SourceBadge, Spinner } from '../design-system'
import { useUI } from '../lib/store'

const KINDS = ['keyword', 'entity', 'country', 'company']
function Watchlist() {
  const qc = useQueryClient()
  const { data } = useApi<any[]>('/api/watchlist')
  const [kind, setKind] = useState('keyword'); const [v, setV] = useState('')
  const [, setSp] = useSearchParams()
  const add = async () => { if (!v.trim()) return; await post('/api/watchlist', { kind, value: v }); setV(''); qc.invalidateQueries({ queryKey: ['/api/watchlist'] }) }
  return (
    <Panel title="Watch list" tone="yellow">
      <div className="text-xs text-dim mb-2">Keywords/entities feed the alert rules (“official text matching a keyword”, “entity cited by N sources”, “sanction on a tracked entity”).</div>
      <div className="flex gap-2 mb-3"><select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map((k) => <option key={k}>{k}</option>)}</select><input value={v} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()} placeholder="Gaza, Rheinmetall, FR…" className="flex-1" /><button className="btn" onClick={add}>＋</button></div>
      {!data?.length && <Empty>Empty.</Empty>}
      {data?.map((w) => <div key={w.id} className="flex items-center justify-between py-1 border-b border-line text-sm"><span><Chip tone="magenta">{w.kind}</Chip> <button style={{ background: 'none', border: 0, color: 'var(--cyan)' }} onClick={() => setSp({ topic: w.value })}>{w.value}</button></span><button className="btn ghost !py-0" onClick={async () => { await del(`/api/watchlist/${w.id}`); qc.invalidateQueries({ queryKey: ['/api/watchlist'] }) }}>✕</button></div>)}
    </Panel>)
}

function Timeline({ topic }: { topic: string }) {
  const [days, setDays] = useState(30)
  const [layers, setLayers] = useState({ articles: true, official: true, alerts: true, market: false })
  const [series, setSeries] = useState('SPX')
  const set = useUI((s) => s.set)
  const { data, isLoading } = useApi<any>(`/api/timeline?topic=${encodeURIComponent(topic)}&days=${days}`)
  const vit = useApi<any>(layers.market ? `/api/vitals/${series}?days=${days}` : null)
  const metas = useApi<Record<string, any[]>>(layers.market ? '/api/vitals' : null)
  const opts = metas.data ? Object.values(metas.data).flat() : []
  const byCountry = useMemo(() => {
    const m: Record<string, Record<string, number>> = {}
    ;(data?.articles || []).forEach((a: any) => { const d = a.ts.slice(0, 10); ((m[a.country || '?'] ||= {})[d] = (m[a.country || '?'][d] || 0) + 1) })
    return m
  }, [data])
  if (isLoading) return <Spinner />
  const dayList: string[] = []
  for (let i = days; i >= 0; i--) dayList.push(new Date(Date.now() - i * 86400000).toISOString().slice(0, 10))
  const top = Object.entries(byCountry).sort((a, b) => Object.values(b[1]).reduce((x, y) => x + y, 0) - Object.values(a[1]).reduce((x, y) => x + y, 0)).slice(0, 8)
  const marks = [...(layers.official ? data.official.map((o: any) => ({ xAxis: o.ts.slice(0, 10), label: { show: false }, lineStyle: { color: '#fcee0a', type: 'dashed' }, tooltip: { formatter: o.title } })) : []), ...(layers.alerts ? data.alerts.map((o: any) => ({ xAxis: o.ts.slice(0, 10), label: { show: false }, lineStyle: { color: '#ff003c' }, tooltip: { formatter: o.title } })) : [])]
  return (
    <div className="grid gap-3">
      <Panel title={`Timeline — “${topic}”`} tone="cyan" actions={<select value={days} onChange={(e) => setDays(+e.target.value)}><option value={7}>7 d</option><option value={30}>30 d</option><option value={90}>90 d</option></select>}>
        <div className="flex gap-3 flex-wrap text-sm mb-2">{(['articles', 'official', 'alerts', 'market'] as const).map((l) => <label key={l}><input type="checkbox" checked={layers[l]} onChange={(e) => setLayers({ ...layers, [l]: e.target.checked })} /> {l === 'articles' ? 'sources by country' : l === 'official' ? 'official decisions (yellow dashes)' : l === 'alerts' ? 'alerts (red)' : 'market overlay'}</label>)}
          {layers.market && <select value={series} onChange={(e) => setSeries(e.target.value)}>{opts.map((m: any) => <option key={m.series} value={m.series}>{m.label}</option>)}</select>}</div>
        {data.articles.length === 0 && data.official.length === 0 ? <Empty>Nothing found for this topic in the last {days} days.</Empty> :
          <Chart height={340} option={{ legend: { textStyle: { color: '#8a8aa0' }, type: 'scroll' }, grid: { left: 44, right: layers.market ? 54 : 14, top: 36, bottom: 28 }, xAxis: { type: 'category', data: dayList, ...axisStyle },
            yAxis: [{ type: 'value', ...axisStyle }, ...(layers.market ? [{ type: 'value', scale: true, ...axisStyle, splitLine: { show: false } }] : [])],
            series: [...(layers.articles ? top.map(([c, m], i) => ({ name: `${flag(c)} ${c === '?' ? 'n/a' : countryName(c)}`, type: 'bar', stack: 'a', data: dayList.map((d) => m[d] || 0), markLine: i === 0 ? { symbol: 'none', data: marks, silent: false } : undefined })) : []),
              ...(layers.market && vit.data ? [{ name: vit.data.meta.label, type: 'line', yAxisIndex: 1, showSymbol: false, lineStyle: { color: '#00ff9f', width: 1.2 }, data: vit.data.points.map((p: any) => [p.ts.slice(0, 10), p.value]) }] : [])] }} />}
      </Panel>
      <div className="grid lg:grid-cols-2 gap-3">
        <Panel title={`Articles (${data.articles.length})`}><div className="max-h-[420px] overflow-y-auto">{data.articles.slice().reverse().map((a: any) => <div key={a.id} className="py-1 border-b border-line text-sm"><span className="mono text-[11px] text-dim">{hhmm(a.ts)}</span> <SourceBadge id={a.source_id} name={a.source_name} /> <a href={a.url} onClick={(e) => { e.preventDefault(); set({ articleId: a.id }) }}>{a.title}</a></div>)}</div></Panel>
        <Panel title={`Official decisions (${data.official.length})`} tone="yellow"><div className="max-h-[420px] overflow-y-auto">{data.official.slice().reverse().map((o: any) => <div key={o.id} className="py-1 border-b border-line text-sm"><span className="mono text-[11px] text-dim">{o.ts.slice(0, 10)}</span> <Chip tone="cyan">{o.origin}</Chip> <a href={o.url} target="_blank" rel="noreferrer">{o.title}</a></div>)}{data.official.length === 0 && <Empty>none</Empty>}</div></Panel>
      </div>
    </div>)
}

export default function Watch() {
  const [sp, setSp] = useSearchParams()
  const topic = sp.get('topic') || ''
  const [t, setT] = useState(topic)
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Watch & timelines</h1>
      <div className="grid lg:grid-cols-[360px_1fr] gap-3">
        <div className="grid gap-3 content-start"><Panel title="Follow a subject over weeks"><div className="flex gap-2"><input value={t} onChange={(e) => setT(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && setSp({ topic: t })} placeholder="a topic, entity, company…" className="flex-1" /><button className="btn" onClick={() => setSp({ topic: t })}>Go</button></div></Panel><Watchlist /></div>
        {topic ? <Timeline topic={topic} key={topic} /> : <Panel><Empty>Pick a subject (or click an item of the watch list) to see its timeline: coverage by country, official decisions, alerts and market overlay.</Empty></Panel>}
      </div>
    </div>)
}
