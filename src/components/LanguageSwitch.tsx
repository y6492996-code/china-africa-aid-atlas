import { useTranslation } from 'react-i18next'

export function LanguageSwitch() {
  const { i18n, t } = useTranslation()

  const switchLanguage = () => {
    const nextLanguage = i18n.resolvedLanguage === 'en' ? 'zh' : 'en'
    void i18n.changeLanguage(nextLanguage)
    window.localStorage.setItem('atlas-language', nextLanguage)
  }

  return (
    <button className="language-switch" type="button" onClick={switchLanguage}>
      <span aria-hidden="true">文 / A</span>
      <span>{t('global.language')}</span>
    </button>
  )
}
