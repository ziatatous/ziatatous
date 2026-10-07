import { useState } from 'react'
import { useApi, useDebounced } from '../lib/hooks'
import { qs } from '../lib/api'
import { Empty, Err, Panel, Spinner } from '../design-system'
import { TopicCard } from './Briefing'

export default function Topics() {
  const [q, setQ] = useState('')
  const [hours, setHours] = useState(48)
  const [country, setCountry] = useState('')
  const dq = useDebounced(q)
  const { data, error, isLoading } = useApi<any[]>(`/api/clusters${qs({ hours, limit: 80, q: dq, country })}`)
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Topics</h1>
      <Panel>
        <div className="flex gap-2 flex-wrap mb-2">
          <input placeholder="filter topics (full text)…" value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 min-w-[200px]" />
          <select value={hours} onChange={(e) => setHours(+e.target.value)}><option value={12}>12 h</option><option value={48}>48 h</option><option value={168}>7 days</option><option value={720}>30 days</option></select>
          <input placeholder="country code (FR)" value={country} onChange={(e) => setCountry(e.target.value.toUpperCase())} className="w-[130px]" maxLength={2} />
        </div>
        {isLoading && <Spinner />}{error && <Err error={error} />}
        {data?.length === 0 && <Empty>No topic matches. A topic needs at least 2 sources.</Empty>}
        {data?.map((c) => <TopicCard key={c.id} c={c} />)}
      </Panel>
    </div>
  )
}
