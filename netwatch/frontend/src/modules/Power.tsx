import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import * as d3 from 'd3'
import { useApi, useDebounced } from '../lib/hooks'
import { get } from '../lib/api'
import { Chip, Empty, Panel, Tone, toneColor } from '../design-system'

const TYPE_TONE: Record<string, Tone> = { person: 'magenta', company: 'cyan', media: 'yellow', state: 'red', org: 'green' }
const REL: Record<string, string> = { owns: 'owns', ceo_of: 'CEO of', board_of: 'board member of', chair_of: 'chair of', held_public_office: 'held public office', head_of_state: 'head of state of', head_of_government: 'head of government of', finances: 'finances', sanctioned_by: 'sanctioned by', lobbies: 'lobbies' }

function Graph({ g, onNode, onEdge, path }: { g: { nodes: any[]; edges: any[]; center?: string }; onNode: (id: string) => void; onEdge: (e: any) => void; path: Set<number> }) {
  const ref = useRef<SVGSVGElement>(null)
  const [size, setSize] = useState({ w: 900, h: 560 })
  useEffect(() => { if (!ref.current) return; const ro = new ResizeObserver(() => ref.current && setSize({ w: ref.current.clientWidth, h: ref.current.clientHeight })); ro.observe(ref.current); return () => ro.disconnect() }, [])
  const [, tick] = useState(0)
  const sim = useRef<any>(null)
  const data = useMemo(() => ({ nodes: g.nodes.map((n) => ({ ...n })), links: g.edges.map((e) => ({ ...e, source: e.src, target: e.dst })) }), [g])
  useEffect(() => {
    const s = d3.forceSimulation(data.nodes as any).force('link', d3.forceLink(data.links as any).id((d: any) => d.id).distance(90).strength(0.5)).force('charge', d3.forceManyBody().strength(-260))
      .force('center', d3.forceCenter(size.w / 2, size.h / 2)).force('collide', d3.forceCollide(24)).on('tick', () => tick((x) => x + 1))
    sim.current = s
    return () => { s.stop() }
  }, [data, size.w, size.h])
  useEffect(() => {
    if (!ref.current) return
    const svg = d3.select(ref.current); const gz = svg.select<SVGGElement>('g.zoom')
    svg.call(d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.2, 4]).on('zoom', (e) => gz.attr('transform', e.transform)) as any)
  }, [])
  const drag = (n: any) => (ev: React.PointerEvent) => {
    ev.stopPropagation(); (ev.target as Element).setPointerCapture(ev.pointerId); n.fx = n.x; n.fy = n.y; sim.current?.alphaTarget(0.3).restart()
    const move = (e: PointerEvent) => { const r = ref.current!.getBoundingClientRect(); const t = d3.zoomTransform(ref.current!); n.fx = (e.clientX - r.left - t.x) / t.k; n.fy = (e.clientY - r.top - t.y) / t.k }
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); n.fx = null; n.fy = null; sim.current?.alphaTarget(0) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  return (
    <svg ref={ref} width="100%" height="560" role="img" aria-label="power network graph" style={{ background: 'var(--bg-void)', touchAction: 'none' }}>
      <g className="zoom">
        {data.links.map((l: any) => { const on = path.has(l.id); return <g key={l.id} onClick={() => onEdge(l)} style={{ cursor: 'pointer' }}>
          <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke={on ? 'var(--yellow)' : 'var(--line)'} strokeWidth={on ? 3 : 0.8 + Math.min(4, l.weight * 3)} />
          <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="transparent" strokeWidth={10} /></g> })}
        {data.nodes.map((n: any) => { const c = toneColor(TYPE_TONE[n.type] || 'neutral'); const center = n.id === g.center
          return <g key={n.id} transform={`translate(${n.x || 0},${n.y || 0})`} onPointerDown={drag(n)} onDoubleClick={() => onNode(n.id)} onClick={() => onNode(n.id)} style={{ cursor: 'pointer' }}>
            <circle r={center ? 11 : 7} fill="var(--bg-panel)" stroke={c} strokeWidth={center ? 3 : 2} />
            <text y={center ? -16 : -12} textAnchor="middle" fill="var(--text)" fontSize={11} fontFamily="Rajdhani" fontWeight={600} style={{ paintOrder: 'stroke', stroke: '#0a0a0f', strokeWidth: 3 }}>{n.label.length > 26 ? n.label.slice(0, 25) + '…' : n.label}</text></g> })}
      </g>
    </svg>)
}

export default function Power() {
  const [sp, setSp] = useSearchParams()
  const node = sp.get('node') || ''
  const [depth, setDepth] = useState(1)
  const [q, setQ] = useState(''); const dq = useDebounced(q)
  const hits = useApi<any[]>(dq.length > 1 ? `/api/graph/search?q=${encodeURIComponent(dq)}` : null)
  const [data, setData] = useState<any>(null)
  const [edge, setEdge] = useState<any>(null)
  const [a, setA] = useState(''), [b, setB] = useState('')
  const [pathRes, setPathRes] = useState<any>(null)
  const [msg, setMsg] = useState('')
  useEffect(() => { if (!node) return; setEdge(null); get(`/api/graph/neighbors?id=${encodeURIComponent(node)}&depth=${depth}`).then(setData).catch((e) => setMsg(e.message)) }, [node, depth])
  const path = useMemo(() => new Set<number>((pathRes?.edges || []).map((e: any) => e.id)), [pathRes])
  const label = (id: string) => data?.nodes.find((n: any) => n.id === id)?.label || id
  const findPath = async () => { setMsg(''); try { const r = await get(`/api/graph/path?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`); setPathRes(r); if (r.found) setData({ nodes: r.nodes, edges: r.edges, center: a }); else setMsg('No path found between these entities') } catch (e: any) { setMsg(e.message) } }
  const pick = (h: any, into?: 'a' | 'b') => { setQ(''); if (into === 'a') setA(h.id); else if (into === 'b') setB(h.id); else setSp({ node: h.id }) }
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Power network</h1>
      <div className="grid lg:grid-cols-[300px_1fr] gap-3">
        <div className="grid gap-3 content-start">
          <Panel title="Find an entity" tone="magenta">
            <input placeholder="person, company, media, state…" value={q} onChange={(e) => setQ(e.target.value)} className="w-full" />
            {hits.data?.map((h) => <div key={h.id} className="flex items-center justify-between gap-1 py-1 border-b border-line text-sm"><button className="text-left" style={{ background: 'none', border: 0, color: 'var(--text)', padding: 0 }} onClick={() => pick(h)}>{h.label} <Chip tone={TYPE_TONE[h.type]}>{h.type}</Chip></button><span><button className="chip" onClick={() => pick(h, 'a')}>A</button> <button className="chip" onClick={() => pick(h, 'b')}>B</button></span></div>)}
            <div className="mt-2 flex items-center gap-2 text-sm"><span className="label">degrees</span>{[1, 2, 3].map((d) => <button key={d} className={`chip ${depth === d ? 'yellow' : ''}`} onClick={() => setDepth(d)}>{d}</button>)}</div>
          </Panel>
          <Panel title="Shortest path" tone="yellow">
            <div className="grid gap-1 text-sm"><div>A: <b>{a ? label(a) : '—'}</b></div><div>B: <b>{b ? label(b) : '—'}</b></div><div className="text-dim text-xs">Use the A / B buttons next to search results.</div>
              <button className="btn" disabled={!a || !b} onClick={findPath}>Find path</button>
              {pathRes?.found && <ol className="m-0 pl-4 text-sm">{pathRes.nodes.map((n: any, i: number) => <li key={n.id}>{n.label}{pathRes.edges[i] && <div className="text-dim text-xs">— {REL[pathRes.edges[i].rel] || pathRes.edges[i].rel} <a href={pathRes.edges[i].source_url} target="_blank" rel="noreferrer">[ref↗]</a></div>}</li>)}</ol>}</div>
          </Panel>
          <Panel title="Legend">
            <div className="grid gap-1 text-xs">{Object.entries(TYPE_TONE).map(([t, tn]) => <div key={t}><span className="inline-block w-3 h-3 mr-2" style={{ background: toneColor(tn) }} />{t}</div>)}
              <div className="text-dim mt-1">Line thickness = importance (stake / amount). Every line carries a source. Click a line for its reference; click a node to re-centre. Drag to move, scroll to zoom.</div></div>
          </Panel>
        </div>
        <div className="grid gap-3 min-w-0">
          <Panel pad={false} title={data ? `${data.nodes.length} entities · ${data.edges.length} sourced links` : 'Graph'}>
            {!node && <Empty>Search an entity (or press ⌘K) to explore its neighbourhood. Try “LVMH”, “Le Monde”, “BlackRock”.</Empty>}
            {data && <Graph g={data} onNode={(id) => setSp({ node: id })} onEdge={setEdge} path={path} />}
            {msg && <div className="mono text-xs text-yellow p-2">{msg}</div>}
          </Panel>
          {edge && <Panel title="Link" tone="yellow" actions={<button className="btn ghost" onClick={() => setEdge(null)}>✕</button>}>
            <div className="text-sm"><b>{label(edge.src?.id ?? edge.src)}</b> — <Chip tone="yellow">{REL[edge.rel] || edge.rel}</Chip> → <b>{label(edge.dst?.id ?? edge.dst)}</b>{edge.label && <span className="text-dim"> ({edge.label})</span>}</div>
            <div className="text-sm mt-1">Source: <a href={edge.source_url} target="_blank" rel="noreferrer">{edge.source_url}</a></div></Panel>}
        </div>
      </div>
    </div>
  )
}
