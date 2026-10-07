import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { get } from './api'

export function useApi<T = any>(url: string | null, opts: { refetch?: number; enabled?: boolean } = {}) {
  return useQuery<T>({ queryKey: [url], queryFn: () => get<T>(url!), enabled: !!url && opts.enabled !== false, refetchInterval: opts.refetch, staleTime: 15_000 })
}

/** True for ~1s when `value` changes after the first render: drives glitch/flash effects for REAL data changes only. */
export function useChanged(value: unknown) {
  const prev = useRef(value)
  const [on, setOn] = useState(false)
  useEffect(() => {
    if (prev.current !== value && prev.current !== undefined) { setOn(true); const t = setTimeout(() => setOn(false), 900); prev.current = value; return () => clearTimeout(t) }
    prev.current = value
  }, [value])
  return on
}

export function useDebounced<T>(v: T, ms = 250) {
  const [d, setD] = useState(v)
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t) }, [v, ms])
  return d
}

/** Subscribe to Server-Sent Events from the backend. */
export function useSSE(onEvent: (e: any) => void) {
  const cb = useRef(onEvent)
  cb.current = onEvent
  useEffect(() => {
    const es = new EventSource('/api/events/stream')
    es.onmessage = (m) => { try { cb.current(JSON.parse(m.data)) } catch { /* ignore */ } }
    return () => es.close()
  }, [])
}
