import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useApi } from '../lib/hooks'
import { get, post, put } from '../lib/api'
import { useUI } from '../lib/store'
import { ago, bytes } from '../lib/format'
import { Chip, Empty, Panel, StatTile, Tabs } from '../design-system'

function FeedRow({ f }: { f: any }) {
  const qc = useQueryClient()
  const [u, setU] = useState(f.url)
  return <tr><td className="mono text-xs">{f.id}</td><td><Chip tone={f.status === 'ok' ? 'green' : f.status === 'new' ? 'neutral' : 'red'}>{f.status}</Chip></td><td className="mono text-[11px] text-dim">{f.last_ok ? ago(f.last_ok) : 'never'}</td>
    <td className="text-xs text-red">{f.last_error}</td><td><input className="mono text-[11px] w-[280px]" value={u} onChange={(e) => setU(e.target.value)} /> <button className="btn ghost !py-0" onClick={async () => { await put(`/api/system/feeds/${f.id}`, { url: u }); qc.invalidateQueries({ queryKey: ['/api/system/feeds'] }) }}>replace</button></td></tr>
}

export default function System() {
  const qc = useQueryClient()
  const ui = useUI()
  const { data: s } = useApi<any>('/api/system', { refetch: 10_000 })
  const [tab, setTab] = useState<'collectors' | 'feeds' | 'data' | 'display'>('collectors')
  const feeds = useApi<any[]>(tab === 'feeds' ? '/api/system/feeds' : null, { refetch: 15_000 })
  const [onlyBad, setOnlyBad] = useState(true)
  const file = useRef<HTMLInputElement>(null)
  const [msg, setMsg] = useState('')
  if (!s) return null
  const act = async (fn: () => Promise<any>, ok: string) => { try { const r = await fn(); setMsg(ok + (r?.path ? ': ' + r.path : '')); qc.invalidateQueries() } catch (e: any) { setMsg('⚠ ' + e.message) } }
  const exportSettings = async () => { const d = await get('/api/backup/export'); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 1)], { type: 'application/json' })); a.download = `netwatch-settings-${new Date().toISOString().slice(0, 10)}.json`; a.click() }
  const importSettings = async (f: File) => act(async () => post('/api/backup/import', JSON.parse(await f.text())), 'imported')
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">System</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel><StatTile label="database" value={bytes(s.db_bytes)} sub={<span className="mono text-[10px]">{s.db_path}</span>} /></Panel>
        <Panel><StatTile label="articles" value={s.counts.articles} sub={`${s.counts.clusters} topics`} /></Panel>
        <Panel><StatTile label="feeds" value={s.feeds.map((x: any) => `${x.n} ${x.status}`).join(' · ') || '0'} tone="green" /></Panel>
        <Panel><StatTile label="retention" value={`${s.retention.fulltext_days}d / ${s.retention.meta_days}d`} sub="full text / metadata" tone="yellow" /></Panel>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'collectors', label: 'Collectors' }, { id: 'feeds', label: 'RSS feeds' }, { id: 'data', label: 'Backup & keys' }, { id: 'display', label: 'Display' }]} />
      {msg && <div className="mono text-xs text-yellow">{msg}</div>}
      {tab === 'collectors' && <Panel title="Collectors" actions={<button className="btn" onClick={() => act(() => post('/api/system/collect'), 'collection started')}>Collect everything now</button>}>
        <div className="overflow-x-auto"><table className="data"><thead><tr><th>Collector</th><th>Family</th><th>Every</th><th>Last success</th><th>Last run</th><th>Items (total)</th><th>Error</th><th /></tr></thead>
          <tbody>{s.collectors.map((c: any) => (
            <tr key={c.name}><td className="mono">{c.name}{c.needs && <div className="text-[10px] text-dim">needs {c.needs}</div>}</td><td>{c.family}</td><td className="mono text-xs">{c.interval_min}m</td>
              <td className="mono text-xs">{c.last_success ? ago(c.last_success) : <span className="text-yellow">never</span>}</td>
              <td>{c.running ? <Chip tone="cyan">running</Chip> : c.last_run ? (c.last_run.ok && (c.last_run.error || '').startsWith('skipped') ? <Chip tone="yellow" title={c.last_run.error}>skipped</Chip> : <Chip tone={c.last_run.ok ? 'green' : 'red'}>{c.last_run.ok ? `ok · ${c.last_run.items}` : 'failed'}</Chip>) : <Chip>idle</Chip>}</td>
              <td className="mono">{c.total_items}</td><td className="text-xs text-red max-w-[360px]">{c.last_run?.error ? <span style={{ color: c.last_run.ok ? 'var(--text-dim)' : undefined }}>{c.last_run.error}</span> : ''}</td>
              <td><button className="btn ghost !py-0" onClick={() => act(() => post(`/api/system/collect?name=${c.name}`), `${c.name} started`)}>run</button></td></tr>))}</tbody></table></div>
      </Panel>}
      {tab === 'feeds' && <Panel title="RSS feeds" actions={<><label className="text-xs"><input type="checkbox" checked={onlyBad} onChange={(e) => setOnlyBad(e.target.checked)} /> problems only</label><button className="btn cyan" onClick={() => act(() => post('/api/system/feeds/check'), 'feed check started (takes a few minutes)')}>Test all feeds</button></>}>
        <div className="text-xs text-dim mb-2">Dead feeds are skipped by the collector. Paste a replacement URL and click “replace”; the feed is retried at the next collection.</div>
        {!feeds.data?.length ? <Empty>—</Empty> : <div className="overflow-x-auto max-h-[60vh]"><table className="data"><thead><tr><th>Feed</th><th>Status</th><th>Last OK</th><th>Error</th><th>URL</th></tr></thead><tbody>{feeds.data.filter((f) => !onlyBad || ['error', 'dead'].includes(f.status)).map((f) => <FeedRow key={f.id + f.url} f={f} />)}</tbody></table></div>}
      </Panel>}
      {tab === 'data' && <div className="grid md:grid-cols-2 gap-3">
        <Panel title="Backup & restore">
          <div className="text-sm text-dim mb-2">Settings = watch list, vocabulary + review state, corrected sources, alert rules, reading log.</div>
          <div className="flex gap-2 flex-wrap"><button className="btn" onClick={exportSettings}>Export settings (JSON)</button><button className="btn ghost" onClick={() => file.current?.click()}>Import settings…</button><button className="btn cyan" onClick={() => act(() => post('/api/backup/db'), 'database copied')}>Copy database to backups/</button>
            <input ref={file} type="file" accept="application/json" hidden onChange={(e) => e.target.files?.[0] && importSettings(e.target.files[0])} /></div>
        </Panel>
        <Panel title="API keys (free) & engines">
          <div className="grid gap-1 text-sm">{Object.entries(s.keys).map(([k, v]) => <div key={k} className="flex justify-between"><span className="mono">{k}</span><Chip tone={v ? 'green' : 'neutral'}>{v ? 'set' : 'not set'}</Chip></div>)}
            <div className="flex justify-between mt-2"><span>Translation: Argos (local)</span><Chip tone={s.translation.argos ? 'green' : 'yellow'}>{s.translation.argos ? 'installed' : 'not installed'}</Chip></div>
            <div className="flex justify-between"><span>Translation: DeepL</span><Chip tone={s.translation.deepl ? 'green' : 'neutral'}>{s.translation.deepl ? 'key set' : 'no key'}</Chip></div>
            <div className="flex justify-between"><span>Clustering</span><Chip tone="cyan">{s.cluster_mode}</Chip></div></div>
          <div className="text-xs text-dim mt-2">Keys live in <code>.env</code> (see <code>.env.example</code>), never in the code. Restart after editing.</div>
        </Panel>
      </div>}
      {tab === 'display' && <Panel title="Display & accessibility">
        <div className="grid gap-2 text-sm"><label><input type="checkbox" checked={ui.calm} onChange={(e) => ui.set({ calm: e.target.checked })} /> Calm mode (disables every animation; also automatic with prefers-reduced-motion)</label>
          <label><input type="checkbox" checked={ui.scanlines} onChange={(e) => ui.set({ scanlines: e.target.checked })} /> Scanlines</label>
          <label><input type="checkbox" checked={ui.sound} onChange={(e) => ui.set({ sound: e.target.checked })} /> Discreet alert sounds</label></div>
      </Panel>}
    </div>
  )
}
