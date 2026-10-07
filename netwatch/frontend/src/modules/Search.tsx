import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi, useDebounced } from '../lib/hooks'
import { qs } from '../lib/api'
import { countryName, langName } from '../lib/format'
import { Empty, Err, Panel, Spinner } from '../design-system'
import ArticleRow from '../shell/ArticleRow'

export default function Search() {
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState(sp.get('q') || '')
  const f = { lang: sp.get('lang') || '', country: sp.get('country') || '', source: sp.get('source') || '', ownership: sp.get('ownership') || '', since: sp.get('since') || '' }
  const [page, setPage] = useState(0)
  const dq = useDebounced(q, 300)
  const facets = useApi<any>('/api/facets')
  const { data, error, isLoading } = useApi<any>(`/api/articles${qs({ q: dq, ...f, limit: 40, offset: page * 40 })}`)
  useEffect(() => setPage(0), [dq, sp])
  const setF = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n, { replace: true }) }
  useEffect(() => { const n = new URLSearchParams(sp); dq ? n.set('q', dq) : n.delete('q'); if (n.toString() !== sp.toString()) setSp(n, { replace: true }) }, [dq]) // eslint-disable-line
  const Sel = ({ k, label, opts }: { k: keyof typeof f; label: string; opts: { v: string; l: string }[] }) => (
    <select value={f[k]} onChange={(e) => setF(k, e.target.value)} aria-label={label}><option value="">{label}</option>{opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}</select>)
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Search</h1>
      <Panel>
        <div className="flex gap-2 flex-wrap">
          <input autoFocus placeholder="full-text search (titles, summaries, locally extracted texts)…" value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 min-w-[240px]" />
          <Sel k="lang" label="language" opts={(facets.data?.langs || []).map((x: any) => ({ v: x.v, l: `${langName(x.v)} (${x.n})` }))} />
          <Sel k="country" label="country" opts={(facets.data?.countries || []).map((x: any) => ({ v: x.v, l: `${countryName(x.v)} (${x.n})` }))} />
          <Sel k="source" label="source" opts={(facets.data?.sources || []).map((x: any) => ({ v: x.v, l: `${x.label || x.v} (${x.n})` }))} />
          <Sel k="ownership" label="ownership" opts={(facets.data?.ownership || []).map((x: any) => ({ v: x.v, l: `${x.v} (${x.n})` }))} />
          <input type="date" value={f.since.slice(0, 10)} onChange={(e) => setF('since', e.target.value ? e.target.value + 'T00:00:00Z' : '')} aria-label="since" />
        </div>
        <div className="mono text-xs text-dim mt-2">{data ? `${data.total} results` : ''}</div>
        {isLoading && <Spinner />}{error && <Err error={error} />}
        {data?.items.length === 0 && <Empty>No result.</Empty>}
        {data?.items.map((a: any) => <ArticleRow key={a.id} a={a} />)}
        {data && data.total > 40 && <div className="flex gap-2 mt-2"><button className="btn ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>← prev</button><span className="mono text-xs self-center">{page + 1} / {Math.ceil(data.total / 40)}</span><button className="btn ghost" disabled={(page + 1) * 40 >= data.total} onClick={() => setPage(page + 1)}>next →</button></div>}
      </Panel>
    </div>
  )
}
