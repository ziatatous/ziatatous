import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en'
import fr from './fr'
import es from './es'

// Strings are looked up by key; the English default is also passed inline at the call site: t('key', 'English').
export const UI_LANGS = [{ code: 'en', label: 'English' }, { code: 'fr', label: 'Français' }, { code: 'es', label: 'Español' }]

let initial = 'en'
try { initial = JSON.parse(localStorage.getItem('nw:uiLang') || '"en"') } catch { /* ignore */ }

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fr: { translation: fr }, es: { translation: es } },
  lng: initial, fallbackLng: 'en', interpolation: { escapeValue: false },
})
export default i18n
