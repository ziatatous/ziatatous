import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useApi, useDebounced } from '../lib/hooks'
import { get, post, put, qs } from '../lib/api'
import { useUI } from '../lib/store'
import { Bar, Chip, CountryBadge, Empty, Err, LangBadge, Panel, SourceBadge, Spinner } from '../design-system'
import { countryName } from '../lib/format'

const TEMPLATE = {
  name: 'New source', country: 'FR', languages: ['fr'], type: 'online', homepage: 'https://',
  founded: { value: 2000, ref: 'https://', checked: new Date().toISOString().slice(0, 10) },
  ownership: { type: 'private', chain: [{ name: 'Owner', kind: 'company', stake: '100%', ref: 'https://' }] },
  financing: [{ kind: 'advertising', note: '', ref: 'https://' }],
  state_affiliated: { value: false, note: '', ref: 'https://' },
  editorial_ratings: [{ org: 'AllSides', rating: '', url: 'https://', date: '' }],
  history: [],
}

function Editor({ id, onClose }: { id: string | null; onClose: () => void }) {
  const qc = useQueryClient()
  const { data } = useApi<any>(id ? `/api/sources/${id}` : null)
  const [sid, setSid] = useState(id || '')
  const [txt, setTxt] = useState<string | null>(null)
  const [msg, setMsg] = useState('')
  const initial = id ? (data ? JSON.stringify(Object.fromEntries(Object.entries(data.data).filter(([k]) => !['wikidata', '_user_edited'].includes(k))), null, 2) : '') : JSON.stringify(TEMPLATE, null, 2)
  const val = txt ?? initial
  const save = async () => {
    try {
      const body = JSON.parse(val)
      const slug = sid.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '')
      if (!slug) throw new Error('id is required (letters, digits, - _)')
      const r = await put(`/api/sources/${slug}`, body)
      setMsg(`saved — completeness ${Math.round(r.completeness * 100)}%`); qc.invalidateQueries({ queryKey: ['/api/sources'] }); qc.invalidateQueries({ queryKey: [`/api/sources/${slug}`] })
    } catch (e: any) { setMsg('⚠ ' + e.message) }
  }
  return (
    <Panel title={id ? `Edit ${id}` : 'Add a source'} tone="yellow" actions={<button className="btn ghost" onClick={onClose}>✕</button>}>
      <div className="text-xs text-dim mb-2">Every field needs a <code>ref</code> URL to count toward completeness; add <code>"checked": "YYYY-MM-DD"</code> once you verified it. Edited sources are never overwritten by YAML reloads.</div>
      {!id && <input placeholder="id (e.g. lemonde)" value={sid} onChange={(e) => setSid(e.target.value)} className="mb-2 w-[260px]" />}
      <textarea value={val} onChange={(e) => setTxt(e.target.value)} spellCheck={false} className="mono w-full h-[360px] text-[12px]" />
      <div className="flex gap-2 items-center mt-2"><button className="btn" onClick={save}>Save</button><span className="mono text-xs text-dim">{msg}</span></div>
    </Panel>
  )
}

export default function Sources() {
  const [q, setQ] = useState(''); const [type, setType] = useState(''); const [own, setOwn] = useState(''); const [cc, setCc] = useState('')
  const [edit, setEdit] = useState<string | null | undefined>(undefined)
  const dq = useDebounced(q)
  const set = useUI((s) => s.set)
  const { data, error, isLoading } = useApi<any[]>(`/api/sources${qs({ q: dq, type, country: cc })}`)
  const rows = (data || []).filter((s) => !own || s.ownership_type === own)
  const countries = [...new Set((data || []).map((s) => s.country).filter(Boolean))].sort()
  const qc = useQueryClient()
  const reverifyAll = async () => { await post('/api/system/collect?name=wikidata_sources'); qc.invalidateQueries({ queryKey: ['/api/sources'] }) }
  return (
    <div className="grid gap-3">
      <div className="flex justify-between items-center flex-wrap gap-2"><h1 className="hud text-2xl m-0">Sources</h1><div className="flex gap-2"><button className="btn cyan" onClick={reverifyAll} title="Runs the Wikidata enrichment in the background">Re-verify all (Wikidata)</button><button className="btn" onClick={() => setEdit(null)}>＋ Add source</button></div></div>
      {edit !== undefined && <Editor id={edit} onClose={() => setEdit(undefined)} key={String(edit)} />}
      <Panel>
        <div className="flex gap-2 flex-wrap mb-2">
          <input placeholder="search a source…" value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 min-w-[200px]" />
          <select value={cc} onChange={(e) => setCc(e.target.value)}><option value="">country</option>{countries.map((c) => <option key={c} value={c}>{countryName(c)}</option>)}</select>
          <select value={type} onChange={(e) => setType(e.target.value)}><option value="">type</option>{['press', 'tv', 'agency', 'online', 'blog', 'institution', 'ngo', 'thinktank', 'primary'].map((t) => <option key={t}>{t}</option>)}</select>
          <select value={own} onChange={(e) => setOwn(e.target.value)}><option value="">ownership</option>{['state', 'public', 'private', 'foundation', 'nonprofit', 'cooperative', 'independent', 'unknown'].map((t) => <option key={t}>{t}</option>)}</select>
        </div>
        <div className="mono text-xs text-dim mb-1">{rows.length} sources · fiche completeness = fields carrying a reference URL</div>
        {isLoading && <Spinner />}{error && <Err error={error} />}
        {rows.length === 0 && !isLoading && <Empty>No source.</Empty>}
        <div className="overflow-x-auto"><table className="data"><thead><tr><th>Source</th><th>Country</th><th>Lang</th><th>Type</th><th>Ownership</th><th>Articles</th><th>Fiche</th><th>Verified</th><th /></tr></thead>
          <tbody>{rows.map((s) => (
            <tr key={s.id}>
              <td><SourceBadge id={s.id} name={s.name} ownership={s.ownership_type} state={s.state_affiliated} /></td>
              <td><CountryBadge cc={s.country} /></td><td>{s.languages.map((l: string) => <LangBadge key={l} lang={l} />)}</td><td className="text-dim">{s.type}</td>
              <td><Chip tone={s.ownership_type === 'state' ? 'red' : s.ownership_type === 'unknown' ? 'neutral' : 'cyan'}>{s.ownership_type}</Chip></td>
              <td className="mono">{s.articles}</td>
              <td style={{ width: 110 }}><div className="flex items-center gap-2"><Bar value={s.completeness} max={1} tone={s.completeness >= .7 ? 'green' : s.completeness >= .4 ? 'yellow' : 'red'} /><span className="mono text-xs">{Math.round(s.completeness * 100)}</span></div></td>
              <td className="mono text-xs text-dim">{s.verified_at || <span className="text-yellow">to verify</span>}</td>
              <td><button className="btn ghost !py-0 !text-[11px]" onClick={() => setEdit(s.id)}>edit</button></td>
            </tr>))}</tbody></table></div>
      </Panel>
    </div>
  )
}
