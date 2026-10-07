import { useState } from 'react'
import { Chart, Chip, CountryBadge, Decrypt, Gauge, LangBadge, Legend, Panel, SourceBadge, Sparkline, StatTile, Tabs, axisStyle } from '../design-system'
import { useUI } from '../lib/store'

/** Design-system demo page. Values are static samples, clearly labelled as such. */
export default function Design() {
  const ui = useUI()
  const [tab, setTab] = useState('a')
  const [n, setN] = useState(41.2)
  const [fresh, setFresh] = useState(0)
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Design system</h1>
      <div className="text-dim text-sm">Every colour has a meaning; effects only fire on real data changes. Below, the samples are static demo values and the two buttons simulate a data change.</div>
      <div className="grid lg:grid-cols-2 gap-3">
        <Panel title="Colour legend" tone="yellow"><Legend /></Panel>
        <Panel title="Typography">
          <div className="hud text-xl">Rajdhani — titles & HUD</div><div className="big text-2xl text-cyan">12 345.67 Orbitron</div>
          <div className="mono">JetBrains Mono — 2026-10-07T08:00:00Z</div><div className="reading !text-[15px]">Inter — long-form article text must remain comfortable to read at length, with generous line height and a 70-character measure.</div>
        </Panel>
        <Panel title="Panels (tones)" >
          <div className="grid grid-cols-2 gap-2">{(['neutral', 'cyan', 'yellow', 'red', 'green', 'magenta'] as const).map((t) => <Panel key={t} title={t} tone={t}><span className="text-dim text-xs">bevelled corners</span></Panel>)}</div>
        </Panel>
        <Panel title="HUD components">
          <div className="flex gap-6 flex-wrap items-end"><StatTile label="stat tile" value={n.toFixed(1)} delta={n - 40} changed={fresh > 0} /><div className="w-[160px]"><div className="label">gauge</div><Gauge value={n} min={20} max={60} thresholds={{ above: 50 }} /></div><div><div className="label">sparkline</div><Sparkline data={[3, 4, 3, 5, 6, 5, 8, 7, 9]} tone="neutral" /></div></div>
          <div className="flex gap-2 mt-3 flex-wrap"><button className="btn" onClick={() => { setN((x) => x + 3.1); setFresh((x) => x + 1); setTimeout(() => setFresh(0), 900) }}>simulate data change (glitch once)</button><button className="btn cyan" onClick={() => setFresh(fresh + 1)}>decrypt: <Decrypt text="FRESH HEADLINE ARRIVED" fresh /></button></div>
          <div className="flex gap-1 flex-wrap mt-3"><Chip>neutral</Chip><Chip tone="cyan">info</Chip><Chip tone="yellow">vigilance</Chip><Chip tone="red">critical</Chip><Chip tone="green">ok</Chip><Chip tone="magenta">entity</Chip><LangBadge lang="fr" /><CountryBadge cc="ES" name />
            <SourceBadge id="x" name="private" ownership="private" /><SourceBadge id="x" name="state" ownership="state" state /><SourceBadge id="x" name="foundation" ownership="foundation" /></div>
          <div className="mt-3"><Tabs value={tab} onChange={setTab} tabs={[{ id: 'a', label: 'Tab A' }, { id: 'b', label: 'Tab B' }]} /></div>
        </Panel>
        <Panel title="Chart (ECharts, themed)" tone="cyan"><Chart height={160} option={{ xAxis: { type: 'category', data: ['A', 'B', 'C', 'D', 'E'], ...axisStyle }, yAxis: { type: 'value', ...axisStyle }, series: [{ type: 'bar', data: [5, 9, 3, 7, 4], itemStyle: { color: '#00f0ff' } }] }} /></Panel>
        <Panel title="Display options"><div className="grid gap-2 text-sm"><label><input type="checkbox" checked={ui.calm} onChange={(e) => ui.set({ calm: e.target.checked })} /> Calm mode</label><label><input type="checkbox" checked={ui.scanlines} onChange={(e) => ui.set({ scanlines: e.target.checked })} /> Scanlines</label></div></Panel>
      </div>
    </div>
  )
}
