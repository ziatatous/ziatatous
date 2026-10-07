import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Shell from './shell/Shell'
import { Spinner } from './design-system'

const L = (f: () => Promise<any>) => lazy(f)
const Briefing = L(() => import('./modules/Briefing'))
const Topics = L(() => import('./modules/Topics'))
const Cross = L(() => import('./modules/Cross'))
const Sources = L(() => import('./modules/Sources'))
const World = L(() => import('./modules/World'))
const Corpos = L(() => import('./modules/Corpos'))
const Vitals = L(() => import('./modules/Vitals'))
const Power = L(() => import('./modules/Power'))
const Official = L(() => import('./modules/Official'))
const Alerts = L(() => import('./modules/Alerts'))
const Agenda = L(() => import('./modules/Agenda'))
const Watch = L(() => import('./modules/Watch'))
const Search = L(() => import('./modules/Search'))
const Languages = L(() => import('./modules/Languages'))
const System = L(() => import('./modules/System'))
const Design = L(() => import('./modules/Design'))

export default function App() {
  return (
    <Shell>
      <Suspense fallback={<Spinner label="loading module…" />}>
        <Routes>
          <Route path="/" element={<Briefing />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/topics/:id" element={<Cross />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/world" element={<World />} />
          <Route path="/world/:code" element={<World />} />
          <Route path="/corpos" element={<Corpos />} />
          <Route path="/corpos/:id" element={<Corpos />} />
          <Route path="/vitals" element={<Vitals />} />
          <Route path="/power" element={<Power />} />
          <Route path="/official" element={<Official />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/agenda" element={<Agenda />} />
          <Route path="/watch" element={<Watch />} />
          <Route path="/search" element={<Search />} />
          <Route path="/languages" element={<Languages />} />
          <Route path="/system" element={<System />} />
          <Route path="/design" element={<Design />} />
          <Route path="*" element={<Briefing />} />
        </Routes>
      </Suspense>
    </Shell>
  )
}
