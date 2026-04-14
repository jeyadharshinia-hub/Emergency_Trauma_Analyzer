/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useMemo, useState } from 'react'
import { labels } from '../i18n'

const LangContext = createContext(null)

export function LangProvider({ children }) {
  const initial = localStorage.getItem('eta_lang') || 'en'
  const [lang, setLang] = useState(initial === 'ta' ? 'ta' : 'en')

  const setLanguage = (value) => {
    const next = value === 'ta' ? 'ta' : 'en'
    setLang(next)
    localStorage.setItem('eta_lang', next)
  }

  const t = useMemo(() => labels[lang], [lang])
  return (
    <LangContext.Provider value={{ lang, setLanguage, t }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLang() {
  const ctx = useContext(LangContext)
  if (!ctx) {
    throw new Error('useLang must be used inside LangProvider')
  }
  return ctx
}
