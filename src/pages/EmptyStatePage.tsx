import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { PageKey } from '../app/routes'

interface EmptyStatePageProps {
  pageKey: PageKey
}

export function EmptyStatePage({ pageKey }: EmptyStatePageProps) {
  const { t } = useTranslation()

  return (
    <main id="main-content" className="page-shell">
      <header className="page-heading">
        <p className="eyebrow">{t(`nav.${pageKey}`)}</p>
        <h1>{t(`pages.${pageKey}.title`)}</h1>
        <p>{t(`pages.${pageKey}.description`)}</p>
      </header>
      <section className="empty-state">
        <span className="empty-badge">{t('pages.emptyBadge')}</span>
        <div className="empty-visual" aria-hidden="true">
          <i /><i /><i /><i /><i />
        </div>
        <h2>{t('pages.emptyTitle')}</h2>
        <p>{t('pages.emptyBody')}</p>
        <Link className="text-link" to="/methods">{t('global.learnMore')} →</Link>
      </section>
    </main>
  )
}
