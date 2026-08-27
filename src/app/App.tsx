import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { routes, type PageKey } from './routes'
import { SiteHeader } from '../components/SiteHeader'
import { SiteFooter } from '../components/SiteFooter'
import { HomePage } from '../pages/HomePage'
import { DatabasesPage } from '../pages/DatabasesPage'
import { TrendsPage } from '../pages/TrendsPage'
import { CountriesPage } from '../pages/CountriesPage'
import { EmptyStatePage } from '../pages/EmptyStatePage'
import { MethodsPage } from '../pages/MethodsPage'
import { MatchReviewPage } from '../pages/MatchReviewPage'
import { FindingsPage } from '../pages/FindingsPage'

function DocumentMetadata() {
  const { t, i18n } = useTranslation()
  const location = useLocation()

  useEffect(() => {
    document.documentElement.lang = i18n.resolvedLanguage === 'en' ? 'en' : 'zh-CN'
    const route = routes.find((item) => item.path === location.pathname)
    const pageTitle = route && route.key !== 'home' ? t(`pages.${route.key}.title`) : t('meta.title')
    document.title = route?.key === 'home' ? pageTitle : `${pageTitle} · ${t('meta.title')}`
    const description = document.querySelector('meta[name="description"]')
    description?.setAttribute('content', t('meta.description'))
  }, [i18n.resolvedLanguage, location.pathname, t])

  return null
}

export default function App() {
  const { t } = useTranslation()

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">{t('global.skip')}</a>
      <DocumentMetadata />
      <SiteHeader />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/databases" element={<DatabasesPage />} />
        <Route path="/trends" element={<TrendsPage />} />
        <Route path="/countries" element={<CountriesPage />} />
        <Route path="/methods" element={<MethodsPage />} />
        <Route path="/review" element={<MatchReviewPage />} />
        <Route path="/findings" element={<FindingsPage />} />
        {routes.slice(4).filter((route) => !['methods', 'review', 'findings'].includes(route.key)).map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={<EmptyStatePage pageKey={route.key as PageKey} />}
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <SiteFooter />
    </div>
  )
}
