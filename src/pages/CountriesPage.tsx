import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useDashboardData } from '../data/dashboard'

type SortMode = 'records' | 'sources' | 'name'
const numberFormatter = new Intl.NumberFormat('en-US')

function compactNumber(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return numberFormatter.format(value)
}

export function CountriesPage() {
  const { i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const { data, failed } = useDashboardData()
  const [query, setQuery] = useState('')
  const [minimumSources, setMinimumSources] = useState(0)
  const [sortMode, setSortMode] = useState<SortMode>('records')

  const copy = isEnglish ? {
    kicker: 'COUNTRY / COVERAGE', title: 'Country ranking', body: 'Filter and rank countries by name, record count and source coverage.', search: 'Search country or ISO code', minimum: 'Minimum sources', sort: 'Sort', records: 'Records', sources: 'Sources', name: 'Name', results: 'Countries shown', observations: 'Source records', median: 'Median coverage', years: 'Observed span', open: 'Open map', noResults: 'No country matches these filters.', failed: 'Data could not be loaded. Confirm that the local site is running, then refresh this page.',
  } : {
    kicker: '国家 / 覆盖', title: '国家排名', body: '按国家名称、记录数和数据源覆盖数量筛选排序。', search: '搜索国家或ISO代码', minimum: '最低来源数', sort: '排序方式', records: '记录数量', sources: '来源数量', name: '国家名称', results: '当前国家', observations: '来源记录', median: '覆盖中位数', years: '观测跨度', open: '打开地图', noResults: '没有符合当前条件的国家。', failed: '数据加载失败，请确认本地网站已启动后刷新页面。',
  }

  const sourceLabels = useMemo(() => Object.fromEntries((data?.sources ?? []).map((source) => [source.id, source.label])), [data])
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return Object.values(data?.countries ?? {}).filter((country) => country.sourceCount >= minimumSources && (!normalized || `${country.nameZh} ${country.nameEn} ${country.iso3}`.toLowerCase().includes(normalized))).sort((a, b) => {
      if (sortMode === 'sources') return b.sourceCount - a.sourceCount || b.records - a.records
      if (sortMode === 'name') return isEnglish ? a.nameEn.localeCompare(b.nameEn) : a.nameZh.localeCompare(b.nameZh, 'zh-CN')
      return b.records - a.records
    })
  }, [data, query, minimumSources, sortMode, isEnglish])
  const totalRecords = filtered.reduce((sum, country) => sum + country.records, 0)
  const sourceCounts = filtered.map((country) => country.sourceCount).sort((a, b) => a - b)
  const medianCoverage = sourceCounts.length ? sourceCounts[Math.floor(sourceCounts.length / 2)] : 0

  if (failed) return <main id="main-content" className="analytics-state">{copy.failed}</main>

  return (
    <main id="main-content" className="analytics-page countries-page">
      <header className="analytics-hero">
        <span>{copy.kicker}</span>
        <h1>{copy.title}</h1>
        <p>{copy.body}</p>
      </header>

      <section className="country-toolbar">
        <label className="country-search"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={copy.search} aria-label={copy.search} /></label>
        <div className="coverage-filter"><span>{copy.minimum}</span>{[0, 3, 6, 9, 12].map((value) => <button key={value} className={minimumSources === value ? 'active' : ''} onClick={() => setMinimumSources(value)}>{value === 0 ? 'ALL' : `${value}+`}</button>)}</div>
        <label className="sort-select"><span>{copy.sort}</span><select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)}><option value="records">{copy.records}</option><option value="sources">{copy.sources}</option><option value="name">{copy.name}</option></select></label>
      </section>

      <section className="country-overview">
        <article><span>{copy.results}</span><strong>{filtered.length}</strong></article>
        <article><span>{copy.observations}</span><strong>{compactNumber(totalRecords)}</strong></article>
        <article><span>{copy.median}</span><strong>{medianCoverage}<small>/12</small></strong></article>
      </section>

      <section className="country-directory" aria-live="polite">
        {filtered.length ? filtered.map((country, index) => {
          const topSources = Object.entries(country.sourceCounts).sort((a, b) => b[1] - a[1]).slice(0, 3)
          return <article className="country-row" key={country.iso3}><span className="country-index">{String(index + 1).padStart(2, '0')}</span><div className="country-identity"><small>{country.iso3}</small><h2>{isEnglish ? country.nameEn : country.nameZh}</h2><p>{isEnglish ? country.nameZh : country.nameEn}</p></div><div className="coverage-meter"><span>{copy.sources}<b>{country.sourceCount}/12</b></span><i><b style={{ width: `${(country.sourceCount / 12) * 100}%` }} /></i><div>{topSources.map(([id]) => <em key={id}>{sourceLabels[id] ?? id}</em>)}</div></div><dl><div><dt>{copy.records}</dt><dd>{compactNumber(country.records)}</dd></div><div><dt>{copy.years}</dt><dd>{country.yearMin ?? '—'}—{country.yearMax ?? '—'}</dd></div></dl><Link to={`/?country=${country.iso3}`}>{copy.open}<span>↗</span></Link></article>
        }) : <div className="directory-empty">{copy.noResults}</div>}
      </section>
    </main>
  )
}
