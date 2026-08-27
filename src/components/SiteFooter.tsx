import { useTranslation } from 'react-i18next'

export function SiteFooter() {
  const { t } = useTranslation()
  return <footer className="site-footer"><div className="footer-inner"><p>{t('footer.statement')}</p><p>© 2026 {t('footer.copyright')}</p></div></footer>
}
