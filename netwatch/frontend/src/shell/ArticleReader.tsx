import { useEffect, useRef, useState } from 'react'
import { useUI } from '../lib/store'
import { useApi } from '../lib/hooks'
import { get, post } from '../lib/api'
import { Chip, CountryBadge, Err, LangBadge, Panel, SourceBadge, Spinner, Tabs } from '../design-system'
import { hhmm, langName } from '../lib/format'

type Mode = 'original' | 'translated' | 'bilingual'
const TTS: Record<string, string> = { en: 'en-US', fr: 'fr-FR', es: 'es-ES', de: 'de-DE', it: 'it-IT', pt: 'pt-PT', ar: 'ar-SA', ru: 'ru-RU', zh: 'zh-CN', ja: 'ja-JP', tr: 'tr-TR', fa: 'fa-IR', hi: 'hi-IN', uk: 'uk-UA', ko: 'ko-KR', nl: 'nl-NL', ca: 'ca-ES' }

/** Reader drawer: original (default) / machine-translated / bilingual sentence-aligned; click a word for definition + vocabulary. */
export default function ArticleReader() {
  const { articleId, set, uiLang } = useUI()
  const { data: a, error } = useApi<any>(articleId ? `/api/articles/${articleId}` : null)
  const [mode, setMode] = useState<Mode>('original')
  const [full, setFull] = useState<string | null>(null)
  const [fullErr, setFullErr] = useState('')
  const [target, setTarget] = useState(uiLang)
  const [tr, setTr] = useState<any>(null)
  const [trErr, setTrErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [word, setWord] = useState<any>(null)
  const t0 = useRef(Date.now())

  useEffect(() => { setMode('original'); setFull(null); setFullErr(''); setTr(null); setTrErr(''); setWord(null); t0.current = Date.now() }, [articleId])
  useEffect(() => { if (a?.full_text) setFull(a.full_text) }, [a])
  useEffect(() => () => { // log reading time per language on close
    const secs = Math.round((Date.now() - t0.current) / 1000)
    if (articleId && a?.lang && secs > 5) post('/api/lang/log', { lang: a.lang, seconds: Math.min(secs, 1800) }).catch(() => {})
  }, [articleId]) // eslint-disable-line

  if (!articleId) return null
  const body = full || a?.summary || ''
  const dst = target === a?.lang ? (a?.lang === 'en' ? 'fr' : 'en') : target

  const fetchFull = async () => { setBusy(true); setFullErr(''); try { const r = await post(`/api/articles/${articleId}/fulltext`); setFull(r.text) } catch (e: any) { setFullErr(e.message) } setBusy(false) }
  const translate = async (m: Mode) => {
    setMode(m); setTrErr('')
    if (m === 'original') return
    setBusy(true)
    try {
      if (m === 'translated') setTr(await post('/api/translate', { text: `${a.title}\n\n${body}`, src: a.lang, dst }))
      else setTr(await post('/api/translate/bilingual', { text: body, src: a.lang, dst }))
    } catch (e: any) { setTrErr(e.message); setTr(null) }
    setBusy(false)
  }
  const clickWord = async (w: string, sentence: string) => {
    const clean = w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
    if (!clean) return
    setWord({ word: clean, sentence, loading: true })
    try { const d = await get(`/api/lang/define?word=${encodeURIComponent(clean)}&lang=${a.lang}&target=${dst}`); setWord({ ...d, sentence }) } catch { setWord({ word: clean, sentence, definitions: [] }) }
  }
  const speak = (txt: string) => { try { const u = new SpeechSynthesisUtterance(txt); u.lang = TTS[a.lang] || a.lang; speechSynthesis.cancel(); speechSynthesis.speak(u) } catch { /* no TTS */ } }
  const addVocab = async () => { await post('/api/vocab', { lang: a.lang, word: word.word, translation: word.translation || word.definitions?.[0]?.text?.slice(0, 120), context: word.sentence, article_id: a.id }); setWord({ ...word, added: true }) }

  const words = (text: string) => text.split(/(\s+)/).map((tok, i) => /\s+/.test(tok) ? tok : <span key={i} className="w" onClick={() => clickWord(tok, sentenceOf(text, tok))}>{tok}</span>)
  const sentenceOf = (text: string, tok: string) => (text.split(/(?<=[.!?。！？])\s+/).find((s) => s.includes(tok)) || '').slice(0, 300)

  return (
    <aside className="fixed top-0 right-0 bottom-0 z-[65] w-full md:w-[720px] overflow-y-auto border-l border-line" style={{ background: 'var(--bg-void)' }} aria-label="Article reader">
      <div className="p-3 grid gap-3">
        <div className="flex justify-between gap-2">
          <div className="flex gap-1 flex-wrap items-center">
            {a && <><SourceBadge id={a.source_id} name={a.source_name} ownership={a.ownership_type} state={a.state_affiliated} /><LangBadge lang={a.lang} /><CountryBadge cc={a.country} /><Chip>{hhmm(a.published_at)}</Chip></>}
          </div>
          <button className="btn ghost" onClick={() => set({ articleId: null })}>✕</button>
        </div>
        {error && <Err error={error} />}
        {!a && !error && <Spinner />}
        {a && <>
          <h1 className="text-[22px] leading-tight m-0" style={{ fontFamily: 'Inter', textTransform: 'none', letterSpacing: 0 }}>{a.title}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Tabs value={mode} onChange={translate} tabs={[{ id: 'original', label: 'Original' }, { id: 'translated', label: 'Translated' }, { id: 'bilingual', label: 'Bilingual' }]} />
            {mode !== 'original' && <label className="text-xs text-dim">→ <select value={dst} onChange={(e) => { setTarget(e.target.value); setTr(null) }}>{['en', 'fr', 'es', 'de', 'it', 'pt'].filter((l) => l !== a.lang).map((l) => <option key={l} value={l}>{langName(l)}</option>)}</select> <button className="btn ghost" onClick={() => translate(mode)}>↻</button></label>}
            <a className="btn cyan ml-auto" href={a.url} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>Open original ↗</a>
          </div>
          {busy && <Spinner label="working…" />}
          {trErr && <div className="text-yellow text-sm mono">⚠ {trErr}<div className="text-dim">Install Argos Translate (see README) or set DEEPL_API_KEY.</div></div>}
          <Panel pad>
            {mode === 'original' && <div className="reading" lang={a.lang} dir={['ar', 'fa', 'he'].includes(a.lang) ? 'rtl' : 'ltr'}>{words(body)}</div>}
            {mode === 'translated' && tr && <><div className="chip yellow mb-2">⚙ {tr.label} ({tr.engine})</div><div className="reading whitespace-pre-wrap">{tr.text}</div></>}
            {mode === 'bilingual' && tr?.pairs && <><div className="chip yellow mb-2">⚙ {tr.label}</div><table className="data"><tbody>{tr.pairs.map(([o, t]: string[], i: number) => <tr key={i}><td className="reading !text-[15px]" lang={a.lang} style={{ width: '50%' }}>{o}</td><td className="reading !text-[15px] text-dim">{t}</td></tr>)}</tbody></table></>}
            {mode === 'translated' && !tr && !busy && !trErr && <div className="text-dim">…</div>}
          </Panel>
          {!full && <div className="flex gap-2 items-center"><button className="btn" disabled={busy} onClick={fetchFull}>Load full text (local, personal use)</button>{fullErr && <span className="text-yellow text-xs mono">{fullErr}</span>}</div>}
          {full && <div className="text-xs text-dim">Full text extracted locally for personal reading; never redistributed. Original link above.</div>}
          {a.entities?.length > 0 && <div className="flex gap-1 flex-wrap">{a.entities.map((e: string) => <Chip key={e} tone="magenta">{e}</Chip>)}</div>}
          {word && (
            <div className="fixed bottom-3 right-3 z-[70] w-[min(420px,calc(100vw-24px))]"><Panel title={<>{word.word} <span className="text-dim normal-case">({langName(a.lang)})</span></>} tone="cyan" actions={<button className="btn ghost" onClick={() => setWord(null)}>✕</button>}>
              {word.loading ? <Spinner /> : <div className="grid gap-2 text-sm">
                {word.translation && <div><span className="chip yellow">machine translation</span> <b>{word.translation}</b></div>}
                {word.definitions?.map((d: any, i: number) => <div key={i}><span className="chip">{d.pos}</span> {d.text}</div>)}
                {!word.definitions?.length && !word.translation && <div className="text-dim">No entry found (Wiktionary). {word.url && <a href={word.url} target="_blank" rel="noreferrer">try</a>}</div>}
                <div className="text-dim text-xs">“{word.sentence}”</div>
                <div className="flex gap-2"><button className="btn cyan" onClick={() => speak(word.word)}>🔊 Pronounce</button><button className="btn" disabled={word.added} onClick={addVocab}>{word.added ? '✓ in vocabulary' : '＋ Add to vocabulary'}</button>{word.url && <a className="text-xs self-center" href={word.url} target="_blank" rel="noreferrer">Wiktionary ↗</a>}</div>
              </div>}
            </Panel></div>
          )}
        </>}
      </div>
    </aside>
  )
}
