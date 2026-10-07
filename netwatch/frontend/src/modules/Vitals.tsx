import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useApi, useChanged } from '../lib/hooks'
import { put } from '../lib/api'
import { ago, num, pct } from '../lib/format'
import { Chart, axisStyle, Chip, Empty, Err, Gauge, Panel, Sparkline, Spinner, Tone } from '../design-system'

const GROUPS: [string, string][] = [['markets', 'Equity indices & volatility'], ['commodities', 'Commodities'], ['crypto', 'Crypto'], ['fx', 'Currencies'], ['rates', 'Rates & yields'], ['macro', 'Macro']]

function Card({ m, onOpen }: { m: any; onOpen: () => void }) {
  const qc = useQueryClient()
  const changed = useChanged(m.last.value)
  const tone: Tone = (m.change_pct ?? m.change ?? 0) >= 0 ? 'green' : 'red'
  const [edit, setEdit] = useState(false)
  const [above, setAbove] = useState(m.alert_above ?? ''); const [below, setBelow] = useState(m.alert_below ?? ''); const [mv, setMv] = useState(m.alert_move_pct ?? '')
  const save = async () => { await put(`/api/vitals-threshold/${m.series}`, { above: above === '' ? null : +above, below: below === '' ? null : +below, move_pct: mv === '' ? null : +mv }); setEdit(false); qc.invalidateQueries({ queryKey: ['/api/vitals'] }) }
  return (
    <Panel tone={tone === 'red' && Math.abs(m.change_pct ?? 0) > 3 ? 'red' : 'neutral'}>
      <div className="flex justify-between gap-2"><button className="label text-left" style={{ background: 'none', border: 0, padding: 0 }} onClick={onOpen}>{m.label}</button><a href={m.source_url} target="_blank" rel="noreferrer" className="mono text-[10px]" title={`updated ${m.updated}`}>{m.source} ↗</a></div>
      <div className="flex items-end justify-between gap-2"><div><div className={`big text-xl ${changed ? 'glitch-once' : ''}`}>{num(m.last.value)} <span className="text-dim text-xs">{m.unit}</span></div>
        <div className="mono text-xs" style={{ color: `var(--${tone})` }}>{m.change_pct !== null ? pct(m.change_pct) : ''} <span className="text-dim">{m.last.ts}</span></div></div>
        <Sparkline data={m.spark.map((p: any) => p.value)} tone="neutral" /></div>
      <div className="mt-2" title={`10-year range: ${num(m.min)} – ${num(m.max)}`}><Gauge value={m.last.value} min={m.min} max={m.max} tone="cyan" thresholds={{ above: m.alert_above, below: m.alert_below }} />
        <div className="flex justify-between mono text-[10px] text-dim"><span>{num(m.min)}</span><span>10y percentile {m.percentile_10y}</span><span>{num(m.max)}</span></div></div>
      <div className="mt-1">{edit ? <div className="flex gap-1 flex-wrap items-center text-xs"><input className="w-[70px]" placeholder="above" value={above} onChange={(e) => setAbove(e.target.value)} /><input className="w-[70px]" placeholder="below" value={below} onChange={(e) => setBelow(e.target.value)} /><input className="w-[70px]" placeholder="move %" value={mv} onChange={(e) => setMv(e.target.value)} /><button className="btn !py-0" onClick={save}>ok</button></div>
        : <button className="btn ghost !py-0 !text-[11px]" onClick={() => setEdit(true)}>⚑ threshold{m.alert_above || m.alert_below || m.alert_move_pct ? ' ✓' : ''}</button>}</div>
    </Panel>)
}

export default function Vitals() {
  const { data, error, isLoading } = useApi<Record<string, any[]>>('/api/vitals', { refetch: 120_000 })
  const [open, setOpen] = useState<string | null>(null)
  const ser = useApi<any>(open ? `/api/vitals/${open}` : null)
  if (isLoading) return <Spinner />
  if (error) return <Err error={error} />
  const empty = !data || Object.keys(data).length === 0
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Vital signs</h1>
      {empty && <Empty>No indicator collected yet. Collectors: quotes (Stooq), ecb, eurostat, worldbank, fred (key). Use System → collect now.</Empty>}
      {open && ser.data && <Panel title={`${ser.data.meta.label} — ${ser.data.meta.source}`} tone="cyan" actions={<button className="btn ghost" onClick={() => setOpen(null)}>✕</button>}>
        <Chart height={300} option={{ xAxis: { type: 'time', ...axisStyle }, yAxis: { type: 'value', scale: true, ...axisStyle }, dataZoom: [{ type: 'inside' }], series: [{ type: 'line', showSymbol: false, data: ser.data.points.map((p: any) => [p.ts, p.value]), lineStyle: { color: '#00f0ff', width: 1.5 }, areaStyle: { color: 'rgba(0,240,255,.07)' } }] }} />
        <div className="mono text-xs text-dim">source: <a href={ser.data.meta.source_url} target="_blank" rel="noreferrer">{ser.data.meta.source_url}</a> · updated {ago(ser.data.meta.updated)}</div></Panel>}
      {GROUPS.filter(([g]) => data?.[g]?.length).map(([g, title]) => (
        <div key={g}><h2 className="hud text-sm text-dim m-0 mb-1">{title}</h2>
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>{data![g].map((m) => <Card key={m.series} m={m} onOpen={() => setOpen(m.series)} />)}</div></div>))}
      <div className="text-xs text-dim">Green/red = up/down versus the previous observation. The 10-year percentile gives historical context; yellow ticks on a gauge are your alert thresholds.</div>
    </div>
  )
}
