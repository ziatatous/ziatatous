import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useApi } from '../lib/hooks'
import { del, post, put } from '../lib/api'
import { useUI } from '../lib/store'
import { UI_LANGS } from '../i18n'
import { langName, num } from '../lib/format'
import { Bar, Chip, Empty, LangBadge, Panel, StatTile, Tabs } from '../design-system'
import ArticleRow from '../shell/ArticleRow'

const TTS: Record<string, string> = { en: 'en-US', fr: 'fr-FR', es: 'es-ES', de: 'de-DE', it: 'it-IT', pt: 'pt-PT', ar: 'ar-SA', ru: 'ru-RU', zh: 'zh-CN', ja: 'ja-JP', tr: 'tr-TR', fa: 'fa-IR', hi: 'hi-IN', uk: 'uk-UA', ko: 'ko-KR', nl: 'nl-NL', ca: 'ca-ES' }

function Review() {
  const qc = useQueryClient()
  const [lang, setLang] = useState('')
  const { data, refetch } = useApi<any[]>(`/api/vocab/due${lang ? '?lang=' + lang : ''}`)
  const [i, setI] = useState(0); const [show, setShow] = useState(false)
  useEffect(() => { setI(0); setShow(false) }, [lang, data?.length])
  const card = data?.[i]
  const grade = async (q: number) => { await post(`/api/vocab/${card.id}/review`, { quality: q }); setShow(false); setI(i + 1); qc.invalidateQueries({ queryKey: ['/api/lang/stats'] }); if (i + 1 >= (data?.length || 0)) refetch() }
  const speak = () => { try { const u = new SpeechSynthesisUtterance(card.word); u.lang = TTS[card.lang] || card.lang; speechSynthesis.speak(u) } catch { /* none */ } }
  return (
    <Panel title={`Review (spaced repetition SM-2) — ${data?.length ?? 0} due`} tone="cyan" actions={<input placeholder="lang (fr)" value={lang} onChange={(e) => setLang(e.target.value)} className="w-[90px]" />}>
      {!card ? <Empty>Nothing due. Read articles and click words to add vocabulary.</Empty> : (
        <div className="grid gap-3 max-w-[560px]">
          <div className="flex gap-2 items-center"><LangBadge lang={card.lang} /><span className="mono text-xs text-dim">card {i + 1}/{data!.length} · interval {card.interval}d · ease {card.ease}</span></div>
          <div className="big text-3xl text-cyan">{card.word} <button className="btn ghost !py-0" onClick={speak}>🔊</button></div>
          {card.context && <div className="text-dim italic">“{card.context}”</div>}
          {show ? <div className="text-lg">{card.translation || <span className="text-dim">no stored translation</span>}</div> : <button className="btn" onClick={() => setShow(true)}>Show answer</button>}
          {show && <div className="flex gap-2 flex-wrap">{[['Again', 1, 'red'], ['Hard', 3, ''], ['Good', 4, 'cyan'], ['Easy', 5, '']].map(([l, q, c]: any) => <button key={l} className={`btn ${c}`} onClick={() => grade(q)}>{l}</button>)}</div>}
        </div>)}
    </Panel>)
}

export default function Languages() {
  const qc = useQueryClient()
  const ui = useUI()
  const [tab, setTab] = useState<'today' | 'review' | 'deck' | 'stats'>('today')
  const stats = useApi<any>('/api/lang/stats')
  const day = useApi<any[]>('/api/lang/of-the-day')
  const deck = useApi<any[]>(tab === 'deck' ? '/api/vocab' : null)
  const known: string[] = stats.data?.known || ['fr', 'en', 'es']
  const maxRead = Math.max(1, ...(stats.data?.reading || []).map((r: any) => r.seconds))
  const immersion = (l: string) => ui.set({ uiLang: l, immersionDay: new Date().toISOString().slice(0, 10) })
  const saveKnown = async (k: string[]) => { await put('/api/settings/known_langs', { value: k }); qc.invalidateQueries({ queryKey: ['/api/lang/stats'] }); qc.invalidateQueries({ queryKey: ['/api/lang/of-the-day'] }) }
  return (
    <div className="grid gap-3">
      <h1 className="hud text-2xl m-0">Languages</h1>
      <Panel title="Immersion mode" tone="yellow">
        <div className="flex gap-2 flex-wrap items-center text-sm">Interface + briefing in one language for today: {UI_LANGS.map((l) => <button key={l.code} className={`btn ${ui.uiLang === l.code ? '' : 'ghost'}`} onClick={() => immersion(l.code)}>{l.label}</button>)}
          {ui.immersionDay && <span className="mono text-xs text-dim">back to English tomorrow</span>}</div>
        <div className="flex gap-1 flex-wrap items-center mt-2 text-sm"><span className="label">languages I know</span>{['en', 'fr', 'es', 'de', 'it', 'pt', 'ar', 'ru', 'zh', 'ja', 'tr', 'fa', 'hi', 'uk', 'ko', 'nl'].map((l) => <button key={l} className={`chip ${known.includes(l) ? 'green' : ''}`} onClick={() => saveKnown(known.includes(l) ? known.filter((x) => x !== l) : [...known, l])}>{l}</button>)}</div>
      </Panel>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'today', label: 'Language of the day' }, { id: 'review', label: 'Review' }, { id: 'deck', label: 'Vocabulary deck' }, { id: 'stats', label: 'Statistics' }]} />
      {tab === 'today' && <Panel title="A story you already follow, told in a language you don't know yet" tone="cyan">
        {!day.data?.length ? <Empty>No story is currently covered in both a known and an unknown language.</Empty> : day.data.map((d) => (
          <div key={d.cluster_id} className="py-2 border-b border-line"><div className="label">you can read it in {d.known.lang.toUpperCase()}:</div><ArticleRow a={d.known} /><div className="label mt-1">…and try it in {d.langs.map(langName).join(', ')}:</div>{d.unknown.map((a: any) => <ArticleRow key={a.id} a={a} showCluster={false} />)}</div>))}
      </Panel>}
      {tab === 'review' && <Review />}
      {tab === 'deck' && <Panel title="Vocabulary">{!deck.data?.length ? <Empty>Empty. Open an article and click a word.</Empty> : <table className="data"><thead><tr><th>Lang</th><th>Word</th><th>Meaning</th><th>Context</th><th>Due</th><th /></tr></thead><tbody>{deck.data.map((v) => <tr key={v.id}><td><LangBadge lang={v.lang} /></td><td className="font-semibold">{v.word}</td><td>{v.translation}</td><td className="text-dim text-xs">{v.context}</td><td className="mono text-xs">{v.due}</td><td><button className="btn ghost !py-0" onClick={async () => { await del(`/api/vocab/${v.id}`); qc.invalidateQueries({ queryKey: ['/api/vocab'] }) }}>✕</button></td></tr>)}</tbody></table>}</Panel>}
      {tab === 'stats' && <div className="grid md:grid-cols-3 gap-3">
        <Panel title="Words learned"><div className="grid gap-2">{(stats.data?.words || []).map((w: any) => <div key={w.lang} className="flex justify-between"><LangBadge lang={w.lang} /><span className="mono">{w.learned} learned / {w.n} words</span></div>)}{!stats.data?.words?.length && <Empty>—</Empty>}</div></Panel>
        <Panel title="Reading time per language">{(stats.data?.reading || []).map((r: any) => <div key={r.lang} className="grid grid-cols-[90px_1fr_60px] gap-2 items-center text-sm"><span>{langName(r.lang)}</span><Bar value={r.seconds} max={maxRead} tone="magenta" /><span className="mono text-xs text-right">{Math.round(r.seconds / 60)} min</span></div>)}{!stats.data?.reading?.length && <Empty>Open articles to start the counter.</Empty>}</Panel>
        <Panel title="Articles read by language">{(stats.data?.articles_read || []).map((r: any) => <div key={r.lang} className="flex justify-between text-sm"><span>{langName(r.lang)}</span><span className="mono">{r.n}</span></div>)}{!stats.data?.articles_read?.length && <Empty>—</Empty>}</Panel></div>}
    </div>)
}
