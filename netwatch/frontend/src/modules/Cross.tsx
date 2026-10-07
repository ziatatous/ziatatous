import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useApi } from '../lib/hooks'
import { post } from '../lib/api'
import { ago, countryName, flag, langName, hhmm } from '../lib/format'
import { Chart, axisStyle, Chip, Empty, Err, LangBadge, Panel, Spinner, Tabs } from '../design-system'
import { useUI } from '../lib/store'
import { SourceBadge } from '../design-system'

type By = 'country' | 'ownership' | 'lang' | 'source'
function Article({ a, shared }: { a: any; shared: string[] }) {
  const set = useUI((s) => s.set)
  const ui = useUI((s) => s.uiLang)
  const [tr, setTr] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const hl = (txt: string) => txt.split(/(\s+)/).map((w, i) => shared.includes(w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')) ? <span key={i} style={{ color: 'var(--cyan)' }}>{w}</span> : <span key={i}>{w}</span>)
  const translate = async () => { try { const r = await post('/api/translate', { text: `${a.title}\n${a.summary || ''}`, src: a.lang, dst: a.lang === ui ? 'en' : ui }); setTr(r.text) } catch (e: any) { setErr(e.message) } }
  return (
    <div className="py-2 border-b border-line">
      <div className="flex gap-1 flex-wrap items-center mb-1"><SourceBadge id={a.source_id} name={a.source_name} ownership={a.ownership_type} state={a.state_affiliated} /><LangBadge lang={a.lang} /><span className="mono text-[11px] text-dim">{hhmm(a.published_at)}</span></div>
      <a href={a.url} onClick={(e) => { e.preventDefault(); set({ articleId: a.id }) }} style={{ color: 'var(--text)' }} className="font-semibold block">{hl(a.title)}</a>
      {a.summary && <div className="text-dim text-[13px]">{a.summary.slice(0, 260)}</div>}
      {tr ? <div className="text-[13px] mt-1"><span className="chip yellow">machine translation</span> {tr}</div> : <button className="btn ghost mt-1 !text-[11px] !py-0" onClick={translate}>translate</button>}
      {err && <div className="text-yellow text-xs mono">{err}</div>}
    </div>
  )
}

export default function Cross() {
  const { id } = useParams()
  const [by, setBy] = useState<By>('country')
  const { data, error, isLoading } = useApi<any>(`/api/clusters/${id}?by=${by}`)
  if (isLoading) return <Spinner />
  if (error) return <Err error={error} />
  const v = data
  const groups = Object.entries<any[]>(v.groups).sort((a, b) => b[1].length - a[1].length)
  const label = (g: string) => (by === 'country' ? `${flag(g)} ${countryName(g)}` : by === 'lang' ? langName(g) : by === 'ownership' ? g : v.groups[g][0]?.source_name || g)
  const t0 = new Date(v.cluster.first_seen).getTime()
  const tl = v.timeline.map((x: any, i: number) => ({ ...x, h: (new Date(x.at).getTime() - t0) / 3600000, i }))
  return (
    <div className="grid gap-3">
      <div>
        <h1 className="text-xl m-0" style={{ fontFamily: 'Inter', textTransform: 'none', letterSpacing: 0 }}>{v.groups && Object.values<any[]>(v.groups).flat().find((a: any) => a.id === v.cluster.label_article_id)?.title}</h1>
        <div className="flex gap-1 flex-wrap mt-1"><Chip tone="cyan">coverage {v.cluster.score}</Chip><Chip>{v.cluster.n_sources} sources</Chip><Chip>{v.cluster.n_countries} countries</Chip><Chip>{v.cluster.n_langs} languages</Chip><Chip>first {ago(v.cluster.first_seen)}</Chip></div>
      </div>

      <div className="grid lg:grid-cols-3 gap-3">
        <Panel title="Vocabulary comparison (statistical, no generated text)" className="lg:col-span-2">
          <div className="text-xs text-dim mb-2">Terms over-represented in a group's headlines compared with the rest of the story (smoothed log-odds). <span style={{ color: 'var(--cyan)' }}>Cyan</span> = shared by most groups.</div>
          <div className="grid md:grid-cols-2 gap-3">{groups.map(([g]) => <div key={g}><div className="label mb-1">{label(g)}</div><div className="flex gap-1 flex-wrap">{(v.distinctive[g] || []).length ? v.distinctive[g].map((t: any) => <Chip key={t.term} tone="yellow" title={`log-odds ${t.score}`}>{t.term} ×{t.count}</Chip>) : <span className="text-dim text-xs">no distinctive term</span>}</div></div>)}</div>
          <div className="mt-3"><div className="label mb-1">shared vocabulary</div><div className="flex gap-1 flex-wrap">{v.shared_terms.map((t: string) => <Chip key={t} tone="cyan">{t}</Chip>)}</div></div>
          <div className="mt-3"><div className="label mb-1">entities put forward</div><div className="flex gap-1 flex-wrap">{v.top_entities.map((e: any) => <Chip key={e.entity} tone="magenta">{e.entity} · {e.count}</Chip>)}</div></div>
        </Panel>
        <div className="grid gap-3 content-start">
          <Panel title="Silences" tone={v.silent_continents.length ? 'yellow' : 'green'}>
            {v.silent_continents.length ? <div className="text-sm">No collected source from: {v.silent_continents.map((c: string) => <Chip key={c} tone="yellow">{c}</Chip>)} <div className="text-dim text-xs mt-1">Absence in our feeds is not proof of absence in the media: check the source list coverage.</div></div> : <div className="text-sm">All continents are represented.</div>}
          </Panel>
          <Panel title="Primary sources" tone="cyan">
            {v.primary_sources.length ? v.primary_sources.map((p: any) => <div key={p.id} className="text-sm py-1 border-b border-line"><Chip tone="cyan">{p.origin}</Chip> <a href={p.url} target="_blank" rel="noreferrer">{p.title}</a></div>) : <Empty>No matching official document found.</Empty>}
          </Panel>
        </div>
      </div>

      <Panel title="Coverage timeline — who spoke first">
        <Chart height={Math.min(420, 90 + tl.length * 12)} option={{
          grid: { left: 150, right: 20, top: 10, bottom: 28 }, tooltip: { formatter: (p: any) => `${p.data[2]}<br/>${p.data[3]}` },
          xAxis: { type: 'value', name: 'hours after first report', nameLocation: 'middle', nameGap: 20, ...axisStyle },
          yAxis: { type: 'category', inverse: true, data: tl.map((x: any) => `${flag(x.country)} ${x.source}`), ...axisStyle },
          series: [{ type: 'scatter', symbolSize: 10, itemStyle: { color: '#00f0ff' }, data: tl.map((x: any) => [x.h, x.i, x.source, hhmm(x.at)]) }] }} />
      </Panel>

      <Panel title="Narratives" actions={<Tabs value={by} onChange={setBy} tabs={[{ id: 'country', label: 'by country' }, { id: 'ownership', label: 'by ownership' }, { id: 'lang', label: 'by language' }, { id: 'source', label: 'by source' }]} />}>
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {groups.map(([g, arts]) => <div key={g}><div className="hud text-yellow border-b border-line pb-1">{label(g)} <span className="text-dim">· {arts.length}</span></div>{arts.map((a) => <Article key={a.id} a={a} shared={v.shared_terms} />)}</div>)}
        </div>
      </Panel>
    </div>
  )
}
