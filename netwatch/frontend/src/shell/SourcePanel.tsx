import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUI } from '../lib/store'
import { useApi } from '../lib/hooks'
import { post } from '../lib/api'
import { Bar, Chart, axisStyle, Chip, CountryBadge, Empty, Err, LangBadge, Panel, Spinner } from '../design-system'
import OwnershipTree from './OwnershipTree'
import { countryName } from '../lib/format'

const Ref = ({ url, checked }: { url?: string; checked?: string }) => url ? <a href={url} target="_blank" rel="noreferrer" className="mono text-[11px]" title={checked ? `verified ${checked}` : 'not yet verified'}>[ref↗{checked ? ' ' + checked : ' · to verify'}]</a> : <span className="chip yellow">no ref</span>

/** Side panel with the complete, referenced source fiche. */
export default function SourcePanel() {
  const { sourcePanel, set } = useUI()
  const qc = useQueryClient()
  const { data: s, isLoading, error } = useApi<any>(sourcePanel ? `/api/sources/${sourcePanel}` : null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  if (!sourcePanel) return null
  const d = s?.data || {}
  const reverify = async () => {
    setBusy(true); setMsg('')
    try { await post(`/api/sources/${sourcePanel}/reverify`); qc.invalidateQueries({ queryKey: [`/api/sources/${sourcePanel}`] }); setMsg('Wikidata re-checked') } catch (e: any) { setMsg(e.message) }
    setBusy(false)
  }
  return (
    <aside className="fixed top-0 right-0 bottom-0 z-[60] w-full md:w-[520px] overflow-y-auto border-l border-line" style={{ background: 'var(--bg-void)' }} aria-label="Source fiche">
      <div className="p-3 grid gap-3">
        <div className="flex justify-between items-start gap-2">
          <div>
            <h1 className="hud text-xl m-0 text-yellow">{s?.name || sourcePanel}</h1>
            {s && <div className="flex gap-1 flex-wrap mt-1"><CountryBadge cc={s.country} name /> {(d.languages || []).map((l: string) => <LangBadge key={l} lang={l} />)} <Chip>{d.type}</Chip>
              {d.state_affiliated?.value && <Chip tone="red">state-affiliated</Chip>}</div>}
          </div>
          <button className="btn ghost" onClick={() => set({ sourcePanel: null })}>✕</button>
        </div>
        {isLoading && <Spinner />}
        {error && <Err error={error} />}
        {s && <>
          <Panel title="Fiche quality" tone={s.completeness >= .8 ? 'green' : 'yellow'}>
            <div className="flex items-center gap-3"><span className="big text-xl">{Math.round(s.completeness * 100)}%</span><div className="flex-1"><Bar value={s.completeness} max={1} tone={s.completeness >= .8 ? 'green' : 'yellow'} /></div></div>
            <div className="text-xs text-dim mt-1">Last verification: <span className="mono">{s.verified_at || 'never — pre-filled, not yet re-verified'}</span>{s.missing?.length > 0 && <> · missing/unreferenced: {s.missing.join(', ')}</>}</div>
            <div className="flex gap-2 mt-2 items-center"><button className="btn cyan" disabled={busy} onClick={reverify}>Re-verify (Wikidata)</button>{msg && <span className="mono text-xs text-dim">{msg}</span>}</div>
          </Panel>
          <Panel title="Identity">
            <dl className="grid grid-cols-[110px_1fr] gap-y-1 text-sm m-0">
              <dt className="text-dim">Website</dt><dd className="m-0">{d.homepage ? <a href={d.homepage} target="_blank" rel="noreferrer">{d.homepage}</a> : '—'}</dd>
              <dt className="text-dim">Founded</dt><dd className="m-0 mono">{d.founded?.value ?? '—'} <Ref url={d.founded?.ref} checked={d.founded?.checked} /></dd>
              <dt className="text-dim">Country</dt><dd className="m-0">{countryName(s.country)}</dd>
              {d.wikidata && <><dt className="text-dim">Wikidata</dt><dd className="m-0"><a href={d.wikidata.url} target="_blank" rel="noreferrer">{d.wikidata.qid}</a>{d.wikidata.auto_match && <span className="chip yellow ml-1">name match — confirm</span>} <span className="mono text-xs text-dim">{d.wikidata.checked}</span></dd></>}
            </dl>
          </Panel>
          <Panel title="Ownership → ultimate beneficiary" tone="magenta">
            <OwnershipTree media={s.name} chain={d.ownership?.chain || []} />
            {d.wikidata?.owners && Object.keys(d.wikidata.owners).length > 0 && <div className="text-xs mt-2">Wikidata P127: {Object.entries(d.wikidata.owners).map(([q, l]: any) => <a key={q} href={`https://www.wikidata.org/wiki/${q}`} target="_blank" rel="noreferrer" className="chip cyan mr-1">{l || q}</a>)}</div>}
            {s.sibling_assets?.length > 0 && <div className="mt-2"><div className="label">Other assets of the same owner(s)</div><div className="flex gap-1 flex-wrap mt-1">{s.sibling_assets.map((a: any) => <Chip key={a.id} tone="magenta">{a.label}</Chip>)}</div></div>}
          </Panel>
          <Panel title="Financing">
            {(d.financing || []).length ? <ul className="m-0 pl-4 text-sm">{d.financing.map((f: any, i: number) => <li key={i}><b>{f.kind}</b> — {f.note} {f.amount && <span className="mono">({f.amount})</span>} <Ref url={f.ref} checked={f.checked} /></li>)}</ul> : <Empty>not documented yet</Empty>}
          </Panel>
          <Panel title="State status" tone={d.state_affiliated?.value ? 'red' : 'neutral'}>
            {d.state_affiliated ? <div className="text-sm"><b>{d.state_affiliated.value ? 'State-affiliated: YES' : 'State-affiliated: no'}</b> — {d.state_affiliated.note} <Ref url={d.state_affiliated.ref} checked={d.state_affiliated.checked} /></div> : <Empty>not documented yet</Empty>}
          </Panel>
          <Panel title="Press freedom context (RSF)">
            {s.rsf ? <div className="text-sm"><span className="big text-xl text-cyan">#{s.rsf.rank ?? '—'}</span> <span className="text-dim">score {s.rsf.score ?? '—'} · {countryName(s.country)} · {s.rsf.year}</span> <a href={s.rsf.ref} target="_blank" rel="noreferrer" className="mono text-[11px]">[ref↗]</a></div> : <Empty>RSF index not loaded (System → collectors → rsf)</Empty>}
          </Panel>
          <Panel title="Editorial positioning (third parties)">
            <div className="text-xs text-yellow mb-2">⚠ These raters have their own biases and methods. NETWATCH never computes its own score.</div>
            {(d.editorial_ratings || []).length ? <ul className="m-0 pl-4 text-sm">{d.editorial_ratings.map((r: any, i: number) => <li key={i}><b>{r.org}</b>: {r.rating} <a href={r.url} target="_blank" rel="noreferrer" className="mono text-[11px]">[ref↗ {r.date || ''}]</a></li>)}</ul> : <Empty>no third-party rating recorded — add from the Sources screen (AllSides, Ad Fontes, Media Bias/Fact Check)</Empty>}
          </Panel>
          <Panel title="History">
            {(d.history || []).length ? <ul className="m-0 pl-4 text-sm">{d.history.map((h: any, i: number) => <li key={i}><span className="mono">{h.date}</span> {h.event} <Ref url={h.ref} checked={h.checked} /></li>)}</ul> : <Empty>no entries yet</Empty>}
          </Panel>
          <Panel title="Collected coverage" tone="cyan">
            <div className="text-sm mb-1"><b className="big text-lg">{s.stats.total}</b> articles collected</div>
            {s.stats.per_day.length > 1 && <Chart height={120} option={{ xAxis: { type: 'category', data: s.stats.per_day.map((p: any) => p.d.slice(5)), ...axisStyle }, yAxis: { type: 'value', ...axisStyle }, grid: { left: 30, right: 6, top: 8, bottom: 20 }, series: [{ type: 'bar', data: s.stats.per_day.map((p: any) => p.n), itemStyle: { color: '#00f0ff' } }] }} />}
            {s.stats.big_story_coverage && <div className="text-sm mt-2">Big stories covered (14 d): <b>{s.stats.big_story_coverage.covered}</b> / {s.stats.big_story_coverage.of} <span className="text-dim">(median source: {s.stats.big_story_coverage.median_source})</span></div>}
            {s.stats.top_entities.length > 0 && <div className="mt-2"><div className="label">Most cited entities</div><div className="flex gap-1 flex-wrap mt-1">{s.stats.top_entities.map((e: any) => <Chip key={e.entity} tone="magenta">{e.entity} · {e.count}</Chip>)}</div></div>}
            <div className="mt-2 text-xs text-dim">Feeds: {s.feeds.map((f: any) => <span key={f.id} className={`chip ${f.status === 'ok' ? 'green' : f.status === 'new' ? '' : 'red'} mr-1`}>{f.lang}/{f.category}</span>)}</div>
          </Panel>
        </>}
      </div>
    </aside>
  )
}
