import { useState } from 'react'
import { useApi, useDebounced } from '../lib/hooks'
import { qs } from '../lib/api'
import { ago } from '../lib/format'
import { Chip, Empty, Err, Panel, Spinner } from '../design-system'

const THEMES = ['liberties', 'surveillance', 'tax', 'energy', 'defense']
const ORIGINS = [['eurlex', 'EUR-Lex (EU)'], ['boe', 'BOE (Spain)'], ['jorf', 'Journal officiel (France)'], ['sanction', 'Sanctions']]
export default function Official() {
  const [q, setQ] = useState(''); const [theme, setTheme] = useState(''); const [origin, setOrigin] = useState('')
  const dq = useDebounced(q)
  const { data, error, isLoading } = useApi<any[]>(`/api/official${qs({ q: dq, theme, origin, limit: 100 })}`)
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Official — what institutions actually decide</h1>
      <Panel>
        <div className="flex gap-2 flex-wrap mb-2">
          <input placeholder="full-text search in official texts…" value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 min-w-[220px]" />
          <select value={origin} onChange={(e) => setOrigin(e.target.value)}><option value="">all origins</option>{ORIGINS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </div>
        <div className="flex gap-1 flex-wrap mb-3"><span className="label self-center mr-1">Highlighted themes</span>
          {THEMES.map((t) => <button key={t} className={`chip ${theme === t ? 'yellow' : ''}`} onClick={() => setTheme(theme === t ? '' : t)}>{t}</button>)}</div>
        {isLoading && <Spinner />}{error && <Err error={error} />}
        {data?.length === 0 && <Empty>No official text matches (collectors: eurlex, boe, legifrance, sanctions).</Empty>}
        {data?.map((o) => (
          <div key={o.id} className="py-2 border-b border-line">
            <div className="flex gap-1 flex-wrap items-center"><Chip tone="cyan">{o.origin}</Chip>{o.country && <Chip>{o.country}</Chip>}{o.themes.map((t: string) => <Chip key={t} tone="yellow">{t}</Chip>)}<span className="mono text-[11px] text-dim">{o.ts?.slice(0, 10)} · {ago(o.ts)}</span></div>
            <a href={o.url} target="_blank" rel="noreferrer" className="font-semibold">{o.title}</a>
            {o.summary && <div className="text-dim text-[13px] line-clamp-2">{o.summary}</div>}
          </div>))}
      </Panel>
    </div>
  )
}
