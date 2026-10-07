import { useState } from 'react'
import { useApi } from '../lib/hooks'
import { Chart, axisStyle, Chip, Empty, Panel, Tabs } from '../design-system'
import { countryName, flag } from '../lib/format'

const KIND_COL: Record<string, string> = { election: '#ff2a6d', central_bank: '#fcee0a', summit: '#00f0ff', macro: '#8a8aa0', agm: '#00ff9f', other: '#8a8aa0' }
export default function Agenda() {
  const [view, setView] = useState<'list' | 'timeline'>('list')
  const [kind, setKind] = useState('')
  const { data } = useApi<any[]>(`/api/agenda?hours=${24 * 180}${kind ? '&kind=' + kind : ''}`)
  const byDate = (data || []).reduce((m: Record<string, any[]>, e) => { (m[e.date] ||= []).push(e); return m }, {})
  const kinds = ['election', 'central_bank', 'summit', 'macro', 'agm']
  const days = [...new Set((data || []).map((e) => e.date))]
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Agenda</h1>
      <Panel actions={<Tabs value={view} onChange={setView} tabs={[{ id: 'list', label: 'List' }, { id: 'timeline', label: 'Timeline' }]} />}>
        <div className="flex gap-1 flex-wrap mb-3"><button className={`chip ${!kind ? 'yellow' : ''}`} onClick={() => setKind('')}>all</button>{kinds.map((k) => <button key={k} className={`chip ${kind === k ? 'yellow' : ''}`} onClick={() => setKind(k)} style={{ borderLeft: `3px solid ${KIND_COL[k]}` }}>{k}</button>)}</div>
        {!data?.length && <Empty>Agenda is empty. Edit <code>data/agenda.yaml</code> (every entry with its source URL); macro releases load automatically with a FRED key.</Empty>}
        {view === 'list' && Object.entries(byDate).map(([d, es]) => (
          <div key={d} className="grid grid-cols-[110px_1fr] gap-3 py-2 border-b border-line"><div className="mono text-cyan">{d}</div><div className="grid gap-1">{es.map((e: any) => <div key={e.id} className="text-sm flex gap-2 flex-wrap items-center"><Chip>{e.kind}</Chip>{e.country && <Chip>{flag(e.country)} {e.country === 'EU' ? 'EU' : countryName(e.country)}</Chip>}<a href={e.url} target="_blank" rel="noreferrer">{e.title}</a><span className="text-dim text-xs">{e.source}</span></div>)}</div></div>))}
        {view === 'timeline' && !!data?.length && <Chart height={Math.max(160, kinds.length * 60)} option={{ tooltip: { formatter: (p: any) => `${p.data[2]}<br/>${p.data[0]}` }, grid: { left: 90, right: 20, top: 10, bottom: 30 },
          xAxis: { type: 'time', ...axisStyle }, yAxis: { type: 'category', data: kinds, ...axisStyle },
          series: [{ type: 'scatter', symbolSize: 14, data: data.map((e: any) => ({ value: [e.date, e.kind, e.title], itemStyle: { color: KIND_COL[e.kind] || '#8a8aa0' } })) }] }} />}
        {days.length > 0 && <div className="text-xs text-dim mt-2">{days.length} dates · colours: pink election, yellow central bank, cyan summit, grey macro data, green shareholder meeting</div>}
      </Panel>
    </div>
  )
}
