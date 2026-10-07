import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useApi } from '../lib/hooks'
import { post, put } from '../lib/api'
import { useUI } from '../lib/store'
import { ago, hhmm } from '../lib/format'
import { Chip, Empty, Panel, Tabs, Tone } from '../design-system'

const TONE: Record<string, Tone> = { INFO: 'cyan', VIGILANCE: 'yellow', CRITICAL: 'red' }
function RuleRow({ r }: { r: any }) {
  const qc = useQueryClient()
  const [p, setP] = useState(JSON.stringify(r.params))
  const [msg, setMsg] = useState('')
  const save = async (extra: any = {}) => { try { await put(`/api/alert-rules/${r.id}`, { params: JSON.parse(p), ...extra }); setMsg('saved'); qc.invalidateQueries({ queryKey: ['/api/alert-rules'] }) } catch (e: any) { setMsg('⚠ ' + e.message) } }
  return (
    <tr>
      <td><input type="checkbox" checked={!!r.enabled} onChange={(e) => save({ enabled: e.target.checked ? 1 : 0 })} aria-label="enabled" /></td>
      <td><Chip tone={TONE[r.level]}>{r.level}</Chip></td><td>{r.name}<div className="mono text-[11px] text-dim">{r.kind}</div></td>
      <td><input className="mono text-xs w-[260px]" value={p} onChange={(e) => setP(e.target.value)} /> <select value={r.level} onChange={(e) => save({ level: e.target.value })}>{['INFO', 'VIGILANCE', 'CRITICAL'].map((l) => <option key={l}>{l}</option>)}</select> <button className="btn ghost !py-0" onClick={() => save()}>save</button> <span className="mono text-xs text-dim">{msg}</span></td>
    </tr>)
}

export default function Alerts() {
  const qc = useQueryClient()
  const ui = useUI()
  const [tab, setTab] = useState<'center' | 'rules'>('center')
  const [unread, setUnread] = useState(false)
  const alerts = useApi<any[]>(`/api/alerts?limit=200${unread ? '&unread=true' : ''}`, { refetch: 60_000 })
  const rules = useApi<any[]>('/api/alert-rules')
  const refresh = () => { qc.invalidateQueries({ queryKey: ['/api/alerts'] }); qc.invalidateQueries({ queryKey: ['/api/alerts/active'] }) }
  const askNotify = async () => { if (!('Notification' in window)) return; const p = await Notification.requestPermission(); ui.set({ notify: p === 'granted' }) }
  return (
    <div className="grid gap-3">
      <div className="flex justify-between items-center flex-wrap gap-2"><h1 className="hud text-2xl m-0">Alerts</h1>
        <div className="flex gap-2 flex-wrap"><button className="btn cyan" onClick={async () => { await post('/api/alerts/evaluate'); refresh() }}>Evaluate rules now</button><button className="btn ghost" onClick={async () => { await post('/api/alerts/read-all'); refresh() }}>Mark all read</button></div></div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'center', label: 'Alert centre' }, { id: 'rules', label: 'Rules' }]} />
      {tab === 'center' && <Panel>
        <label className="text-sm"><input type="checkbox" checked={unread} onChange={(e) => setUnread(e.target.checked)} /> unread only</label>
        {alerts.data?.length === 0 && <Empty>No alert yet. Rules are evaluated every 10 minutes.</Empty>}
        {alerts.data?.map((a) => (
          <div key={a.id} className="py-2 border-b border-line" style={{ opacity: a.read ? 0.6 : 1 }}>
            <div className="flex gap-2 items-center flex-wrap"><Chip tone={TONE[a.level]}>{a.level}</Chip><b>{a.title}</b><span className="mono text-[11px] text-dim">{hhmm(a.created)} · {ago(a.created)}</span>{!a.read && <button className="btn ghost !py-0 !text-[11px]" onClick={async () => { await post(`/api/alerts/${a.id}/read`); refresh() }}>mark read</button>}</div>
            <div className="text-xs text-dim mt-1"><span className="chip">rule: {a.detail.rule?.name}</span> <span className="mono">{JSON.stringify(a.detail.rule?.params)}</span>
              {a.detail.url && <> · <a href={a.detail.url} target="_blank" rel="noreferrer">source data ↗</a></>}
              {a.detail.cluster_id && <> · <Link to={`/topics/${a.detail.cluster_id}`}>cross-view</Link></>}</div>
            <details className="text-xs"><summary className="cursor-pointer text-dim">data</summary><pre className="mono whitespace-pre-wrap m-0">{JSON.stringify(a.detail, null, 1)}</pre></details>
          </div>))}
      </Panel>}
      {tab === 'rules' && <Panel title="Readable rules — no black box">
        <div className="text-xs text-dim mb-2">Parameters are plain JSON. Examples: <code>{'{"min_mag": 6.5}'}</code>, <code>{'{"factor": 3, "min_countries": 3, "min_sources": 5}'}</code>, <code>{'{"pct": 3}'}</code>. Keyword and entity rules read the Watch list.</div>
        <table className="data"><thead><tr><th>On</th><th>Level</th><th>Rule</th><th>Parameters</th></tr></thead><tbody>{rules.data?.map((r) => <RuleRow key={r.id} r={r} />)}</tbody></table>
        <div className="mt-4 flex gap-4 flex-wrap items-center"><label><input type="checkbox" checked={ui.notify} onChange={(e) => e.target.checked ? askNotify() : ui.set({ notify: false })} /> browser notifications</label><label><input type="checkbox" checked={ui.sound} onChange={(e) => ui.set({ sound: e.target.checked })} /> discreet sound per level</label></div>
      </Panel>}
    </div>
  )
}
