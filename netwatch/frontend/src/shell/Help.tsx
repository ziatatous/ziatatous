import { useUI } from '../lib/store'
import { Legend, Panel } from '../design-system'

const ROWS: [string, string][] = [['Ctrl/⌘ + K', 'Command palette'], ['?', 'This help'], ['/', 'Search'], ['.', 'Calm mode on/off'], ['g then b', 'Briefing'], ['g then t', 'Topics'], ['g then s', 'Sources'], ['g then m', 'World'], ['g then c', 'Corpos'], ['g then v', 'Vitals'], ['g then p', 'Power network'], ['g then o', 'Official'], ['g then a', 'Alerts'], ['g then g', 'Agenda'], ['g then w', 'Watch'], ['g then f', 'Search'], ['g then l', 'Languages'], ['g then y', 'System'], ['Esc', 'Close panels']]
export default function Help() {
  const { helpOpen, set } = useUI()
  if (!helpOpen) return null
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,.6)' }} onClick={() => set({ helpOpen: false })}>
      <div className="w-full max-w-[720px] max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <Panel title="Keyboard shortcuts & colour legend" tone="yellow" actions={<button className="btn ghost" onClick={() => set({ helpOpen: false })}>Esc</button>}>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="grid gap-1">{ROWS.map(([k, v]) => <div key={k} className="flex justify-between gap-3 text-sm"><span className="chip yellow">{k}</span><span className="text-dim">{v}</span></div>)}</div>
            <Legend />
          </div>
        </Panel>
      </div>
    </div>
  )
}
