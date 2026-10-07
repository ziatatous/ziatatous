import { Tone, toneColor } from '../design-system'

const KIND_TONE: Record<string, Tone> = { person: 'magenta', family: 'magenta', company: 'cyan', fund: 'cyan', state: 'red', foundation: 'green', ngo: 'green', cooperative: 'green', organization: 'green' }
/** Ownership chain: ultimate beneficiary at the top, the media at the bottom. Every box links to its reference. */
export default function OwnershipTree({ media, chain }: { media: string; chain: any[] }) {
  const nodes = [...chain].reverse()
  if (!chain.length) return <div className="text-dim text-sm">No ownership chain documented yet.</div>
  const W = 330, H = 46, G = 22
  const total = (nodes.length + 1) * (H + G)
  return (
    <svg width="100%" viewBox={`0 0 ${W + 20} ${total}`} role="img" aria-label="ownership chain">
      {nodes.map((n, i) => {
        const y = i * (H + G) + 4
        const c = toneColor(KIND_TONE[n.kind] || 'neutral')
        return (
          <g key={i}>
            {i > 0 && <line x1={W / 2 + 10} y1={y - G} x2={W / 2 + 10} y2={y} stroke="var(--line)" strokeWidth={2} />}
            <a href={n.ref} target="_blank" rel="noreferrer">
              <rect x={10} y={y} width={W} height={H} fill="var(--bg-void)" stroke={c} />
              <text x={20} y={y + 18} fill="var(--text)" fontSize={13} fontFamily="Rajdhani" fontWeight={600}>{n.name.length > 40 ? n.name.slice(0, 39) + '…' : n.name}</text>
              <text x={20} y={y + 35} fill={c} fontSize={10} fontFamily="JetBrains Mono">{n.kind}{n.stake ? ' · ' + (n.stake.length > 40 ? n.stake.slice(0, 39) + '…' : n.stake) : ''} ↗</text>
            </a>
          </g>
        )
      })}
      {(() => { const y = nodes.length * (H + G) + 4; return (<g><line x1={W / 2 + 10} y1={y - G} x2={W / 2 + 10} y2={y} stroke="var(--line)" strokeWidth={2} /><rect x={10} y={y} width={W} height={H - 8} fill="var(--bg-panel)" stroke="var(--yellow)" /><text x={20} y={y + 24} fill="var(--yellow)" fontSize={13} fontFamily="Rajdhani" fontWeight={700}>{media}</text></g>) })()}
    </svg>
  )
}
