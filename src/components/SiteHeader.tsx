import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { LanguageSwitch } from './LanguageSwitch'

const navigation = [{ path: '/', key: 'home' }, { path: '/databases', key: 'databases' }, { path: '/trends', key: 'trends' }, { path: '/countries', key: 'countries' }, { path: '/findings', key: 'findings' }, { path: '/review', key: 'review' }, { path: '/methods', key: 'methods' }]

export function SiteHeader() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return <header className="site-header"><div className="header-inner"><NavLink className="brand" to="/" onClick={() => setOpen(false)} aria-label={t('brand.shortTitle')}><span className="brand-mark" aria-hidden="true"><i /><i /></span><span className="brand-title">CAAD</span></NavLink><button className="menu-button" type="button" aria-expanded={open} aria-controls="primary-navigation" aria-label={open ? t('nav.close') : t('nav.menu')} onClick={() => setOpen((value) => !value)}><span /><span /></button><nav id="primary-navigation" className={open ? 'primary-nav is-open' : 'primary-nav'}>{navigation.map((route) => <NavLink key={route.path} to={route.path} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? 'active' : undefined} end={route.path === '/'}>{t(`nav.${route.key}`)}</NavLink>)}</nav><LanguageSwitch /></div></header>
}
