import { Link } from 'react-router-dom'
import { useUI } from '../lib/store'
import { ago } from '../lib/format'
import { CountryBadge, Decrypt, LangBadge, SourceBadge } from '../design-system'

export default function ArticleRow({ a, fresh = false, showCluster = true }: { a: any; fresh?: boolean; showCluster?: boolean }) {
  const set = useUI((s) => s.set)
  return (
    <div className={`py-2 border-b border-line ${fresh ? 'flash-new' : ''}`} style={{ opacity: a.read ? 0.7 : 1 }}>
      <div className="flex flex-wrap gap-1 items-center mb-[2px]">
        <SourceBadge id={a.source_id} name={a.source_name} ownership={a.ownership_type} state={a.state_affiliated} />
        <LangBadge lang={a.lang} /><CountryBadge cc={a.country} />
        <span className="mono text-[11px] text-dim">{ago(a.published_at)}</span>
        {showCluster && a.cluster_id && <Link to={`/topics/${a.cluster_id}`} className="chip cyan" title="see how everyone tells it">⇄ cross-view</Link>}
      </div>
      <a href={a.url} onClick={(e) => { e.preventDefault(); set({ articleId: a.id }) }} className="text-[15px] font-semibold block" style={{ color: 'var(--text)' }}>
        <Decrypt text={a.title} fresh={fresh} />
      </a>
      {a.summary && <div className="text-dim text-[13px] line-clamp-2">{a.summary}</div>}
    </div>
  )
}
