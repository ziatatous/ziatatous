import { create } from 'zustand'

type S = {
  calm: boolean; scanlines: boolean; sound: boolean; notify: boolean
  uiLang: string; immersionDay: string | null
  sourcePanel: string | null; articleId: number | null; paletteOpen: boolean; helpOpen: boolean
  set: (p: Partial<S>) => void
}
const load = <T,>(k: string, d: T): T => { try { const v = localStorage.getItem('nw:' + k); return v ? JSON.parse(v) : d } catch { return d } }
const save = (k: string, v: unknown) => { try { localStorage.setItem('nw:' + k, JSON.stringify(v)) } catch { /* private mode */ } }

const reduce = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
export const useUI = create<S>((set) => ({
  calm: load('calm', reduce), scanlines: load('scanlines', true), sound: load('sound', false), notify: load('notify', false),
  uiLang: load('uiLang', 'en'), immersionDay: load('immersionDay', null),
  sourcePanel: null, articleId: null, paletteOpen: false, helpOpen: false,
  set: (p) => set((s) => { Object.entries(p).forEach(([k, v]) => { if (['calm', 'scanlines', 'sound', 'notify', 'uiLang', 'immersionDay'].includes(k)) save(k, v) }); return { ...s, ...p } }),
}))
