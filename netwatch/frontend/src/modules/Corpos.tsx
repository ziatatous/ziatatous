import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useApi } from '../lib/hooks'
import { post } from '../lib/api'
import { ago, flag, num, pct } from '../lib/format'
import { Chart, axisStyle, Chip, Empty, Err, Panel, Spinner, Tabs, Field } from '../design-system'
import ArticleRow from '../shell/ArticleRow'

const SECTORS = ['bigtech', 'finance', 'defense', 'energy', 'pharma', 'agrofood', 'media', 'surveillance']

function List() {
  const [sector, setSector] = useState('')
  const [adding, setAdding] = useState(false)
  const [f, setF] = useState({ name: '', sector: 'bigtech', country: 'US', stooq: '', sec_ticker: '' })
  const qc = useQueryClient()
  const nav = useNavigate()
  const { data, error, isLoading } = useApi<any[]>(`/api/companies${sector ? '?sector=' + sector : ''}`, { refetch: 120_000 })
  return (
    <div className="grid gap-3">
      <div className="flex justify-between flex-wrap gap-2 items-center"><h1 className="hud text-2xl m-0">Corpos</h1><button className="btn" onClick={() => setAdding(!adding)}>＋ Add company</button></div>
      {adding && <Panel title="Add a company" tone="yellow"><div className="grid md:grid-cols-5 gap-2">
        <Field label="name"><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="sector"><select value={f.sector} onChange={(e) => setF({ ...f, sector: e.target.value })}>{SECTORS.map((s) => <option key={s}>{s}</option>)}</select></Field>
        <Field label="country (ISO2)"><input value={f.country} maxLength={2} onChange={(e) => setF({ ...f, country: e.target.value.toUpperCase() })} /></Field>
        <Field label="Stooq symbol"><input placeholder="aapl.us" value={f.stooq} onChange={(e) => setF({ ...f, stooq: e.target.value })} /></Field>
        <Field label="SEC ticker (US)"><input placeholder="AAPL" value={f.sec_ticker} onChange={(e) => setF({ ...f, sec_ticker: e.target.value })} /></Field></div>
        <button className="btn mt-2" disabled={!f.name} onClick={async () => { const r = await post('/api/companies', f); qc.invalidateQueries({ queryKey: ['/api/companies'] }); setAdding(false); nav('/corpos/' + r.id) }}>Save</button></Panel>}
      <Panel>
        <div className="flex gap-1 flex-wrap mb-3"><button className={`chip ${!sector ? 'yellow' : ''}`} onClick={() => setSector('')}>all</button>{SECTORS.map((s) => <button key={s} className={`chip ${sector === s ? 'yellow' : ''}`} onClick={() => setSector(s)}>{s}</button>)}</div>
        {isLoading && <Spinner />}{error && <Err error={error} />}
        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))' }}>
          {data?.map((c) => (
            <Link key={c.id} to={`/corpos/${c.id}`} className="block p-2 border border-line" style={{ color: 'var(--text)', textDecoration: 'none' }}>
              <div className="hud font-semibold">{c.name}</div><div className="flex gap-1 mt-1"><Chip>{c.sector}</Chip><Chip>{flag(c.country)} {c.country}</Chip></div>
              <div className="mono text-sm mt-1">{c.last ? <>{num(c.last.value)} <span style={{ color: (c.change_pct ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>{pct(c.change_pct)}</span></> : <span className="text-dim">no quote</span>}</div>
            </Link>))}
        </div>
        {data?.length === 0 && <Empty>No company.</Empty>}
      </Panel>
    </div>
  )
}

const Facts = ({ rows, empty }: { rows: any[]; empty: string }) => rows?.length ? <>{rows.map((r, i) => <div key={i} className="py-1 border-b border-line text-sm flex gap-2 flex-wrap"><span className="mono text-xs text-dim">{r.ts?.slice(0, 10)}</span><a href={r.url} target="_blank" rel="noreferrer">{r.label}</a>{r.value !== null && r.value !== undefined && <span className="mono">{num(r.value, 0)}</span>}</div>)}</> : <Empty>{empty}</Empty>

function Detail({ id }: { id: string }) {
  const { data: c, error, isLoading } = useApi<any>(`/api/companies/${id}`)
  const [tab, setTab] = useState('market')
  const qc = useQueryClient()
  const [msg, setMsg] = useState('')
  if (isLoading) return <Spinner />
  if (error) return <Err error={error} />
  const f = c.facts
  const base = c.history[0]?.value, ibase = c.index.find((x: any) => x.ts >= c.history[0]?.ts)?.value
  const idxMap: Record<string, number> = Object.fromEntries(c.index.map((x: any) => [x.ts, x.value]))
  const lob = (k: string) => (f[k] || []).slice().sort((a: any, b: any) => a.ts.localeCompare(b.ts))
  const holders = (f.holder || []).filter((h: any) => h.ts === (f.holder || [])[0]?.ts).sort((a: any, b: any) => b.value - a.value)
  const track = async () => { await post('/api/watchlist', { kind: 'company', value: c.name }); setMsg('added to the watch list: entity-mention alerts apply'); qc.invalidateQueries({ queryKey: ['/api/watchlist'] }) }
  return (
    <div className="grid gap-3">
      <div className="flex items-start justify-between flex-wrap gap-2"><div><Link to="/corpos" className="mono text-xs">← all companies</Link><h1 className="hud text-2xl m-0">{c.name}</h1>
        <div className="flex gap-1 flex-wrap mt-1"><Chip>{c.sector}</Chip><Chip>{flag(c.country)} {c.country}</Chip>{c.ticker && <Chip tone="cyan">{c.ticker}</Chip>}{c.data.qid && <a className="chip magenta" href={`https://www.wikidata.org/wiki/${c.data.qid}`} target="_blank" rel="noreferrer">{c.data.qid}{c.data.qid_auto_match ? ' (auto-match: verify)' : ''}</a>}</div></div>
        <div className="flex gap-2 items-center"><button className="btn" onClick={track}>⚑ Track</button><Link className="btn cyan" to={`/power?node=co:${c.id}`} style={{ textDecoration: 'none' }}>⌘ Power network</Link><Link className="btn ghost" to={`/watch?topic=${encodeURIComponent(c.name)}`} style={{ textDecoration: 'none' }}>timeline</Link></div></div>
      {msg && <div className="mono text-xs text-green">{msg}</div>}
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'market', label: 'Market' }, { id: 'holders', label: `Shareholders ${holders.length}` }, { id: 'lobby', label: 'Lobbying' }, { id: 'fines', label: `Fines & sanctions ${(f.regulatory || []).length}` }, { id: 'door', label: `Revolving door ${(f.revolving_door || []).length}` }, { id: 'group', label: 'Subsidiaries & media' }, { id: 'news', label: `News ${c.news.length}` }]} />
      {tab === 'market' && <Panel title="Price vs S&P 500 (rebased to 100)" tone="cyan">
        {c.history.length < 2 ? <Empty>No quote history (check the Stooq symbol; System → collectors → company_quotes).</Empty> :
          <Chart height={320} option={{ legend: { data: [c.name, 'S&P 500'], textStyle: { color: '#8a8aa0' } }, xAxis: { type: 'time', ...axisStyle }, yAxis: { type: 'value', scale: true, ...axisStyle }, dataZoom: [{ type: 'inside' }, { type: 'slider', height: 14 }],
            series: [{ name: c.name, type: 'line', showSymbol: false, lineStyle: { color: '#00f0ff', width: 1.5 }, data: c.history.map((p: any) => [p.ts, (p.value / base) * 100]) },
              { name: 'S&P 500', type: 'line', showSymbol: false, lineStyle: { color: '#8a8aa0', width: 1 }, data: ibase ? c.history.filter((p: any) => idxMap[p.ts]).map((p: any) => [p.ts, (idxMap[p.ts] / ibase) * 100]) : [] }] }} />}
        {c.quote && <div className="mono text-xs text-dim">last {num(c.quote.last.value)} on {c.quote.last.ts} · 10y percentile {c.quote.percentile_10y} · source Stooq</div>}</Panel>}
      {tab === 'holders' && <Panel title="Largest institutional holders (SEC Form 13F, latest filings of tracked managers)">
        {holders.length ? <table className="data"><thead><tr><th>Manager</th><th>Reported value (USD)</th><th>Shares</th><th>Period</th></tr></thead><tbody>{holders.map((h: any, i: number) => <tr key={i}><td><a href={h.url} target="_blank" rel="noreferrer">{h.label}</a></td><td className="mono">{num(h.value, 0)}</td><td className="mono">{num(h.payload.shares, 0)}</td><td className="mono text-xs text-dim">{h.ts}</td></tr>)}</tbody></table> : <Empty>No 13F data (US issuers only; collector edgar_13f). Only a fixed list of the biggest managers is read, so this is a partial view.</Empty>}</Panel>}
      {tab === 'lobby' && <div className="grid md:grid-cols-2 gap-3">
        <Panel title="US lobbying (Senate LDA) — expenses per year" tone="yellow">{lob('lobbying_us').length ? <><Chart height={200} option={{ xAxis: { type: 'category', data: lob('lobbying_us').map((x: any) => x.ts.slice(0, 4)), ...axisStyle }, yAxis: { type: 'value', ...axisStyle }, series: [{ type: 'bar', data: lob('lobbying_us').map((x: any) => x.value), itemStyle: { color: '#fcee0a' } }] }} />
          <div className="flex gap-1 flex-wrap">{Object.entries(lob('lobbying_us').slice(-1)[0]?.payload?.issues || {}).sort((a: any, b: any) => b[1] - a[1]).slice(0, 10).map(([k, n]: any) => <Chip key={k} tone="yellow">{k} · {n}</Chip>)}</div></> : <Empty>No US lobbying data (collector lobbying_us; may need LDA_API_KEY).</Empty>}</Panel>
        <Panel title="EU Transparency Register" tone="yellow"><Facts rows={f.lobbying_eu} empty="No EU register data: download the register export into data/inbox/ (see docs/SOURCES_DATA.md)." /></Panel></div>}
      {tab === 'fines' && <Panel title="Regulator announcements mentioning fines, penalties, settlements, antitrust" tone="red"><Facts rows={f.regulatory} empty="Nothing detected in the configured regulator feeds." />
        <div className="text-xs text-dim mt-2">Sanctions naming this company appear as alerts and in Official → Sanctions (OpenSanctions).</div></Panel>}
      {tab === 'door' && <Panel title="Public ↔ private: executives & board members who held public office (Wikidata)" tone="magenta">
        {(f.revolving_door || []).length ? <table className="data"><thead><tr><th>Person</th><th>Role here</th><th>Public office</th><th>Period</th></tr></thead><tbody>{f.revolving_door.map((r: any, i: number) => <tr key={i}><td><a href={r.url} target="_blank" rel="noreferrer">{r.payload.person}</a></td><td>{r.payload.role}</td><td>{r.payload.office}</td><td className="mono text-xs">{r.payload.start?.slice(0, 4)}–{r.payload.end?.slice(0, 4)}</td></tr>)}</tbody></table> : <Empty>None found (collector wikidata_people; Wikidata coverage is incomplete).</Empty>}</Panel>}
      {tab === 'group' && <Panel title="Owned entities (sourced)" tone="magenta">{c.owned.length ? c.owned.map((o: any) => <div key={o.id} className="py-1 border-b border-line"><Chip tone="magenta">{o.type}</Chip> {o.label} <a href={o.source_url} target="_blank" rel="noreferrer" className="text-xs">[ref↗]</a></div>) : <Empty>No subsidiary or media recorded.</Empty>}</Panel>}
      {tab === 'news' && <Panel title="Articles citing the company">{c.clusters.length > 0 && <div className="mb-2">{c.clusters.map((k: number) => <Link key={k} className="chip cyan mr-1" to={`/topics/${k}`}>⇄ cross-view #{k}</Link>)}</div>}{c.news.length ? c.news.map((a: any) => <ArticleRow key={a.id} a={a} />) : <Empty>No article.</Empty>}</Panel>}
    </div>
  )
}

export default function Corpos() { const { id } = useParams(); return id ? <Detail id={id} key={id} /> : <List /> }
