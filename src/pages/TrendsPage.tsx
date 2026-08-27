import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { recordsInRange, useDashboardData, type CountryData } from '../data/dashboard'

const numberFormatter = new Intl.NumberFormat('en-US')
const rangeStarts = [2000, 2005, 2010, 2015, 2020]

function compactNumber(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return numberFormatter.format(value)
}

function buildSeries(countries: CountryData[], start: number, end: number) {
  const values = new Map<number, number>()
  for (let year = start; year <= end; year += 1) values.set(year, 0)
  countries.forEach((country) => Object.entries(country.yearCounts).forEach(([year, count]) => {
    const numericYear = Number(year)
    if (numericYear >= start && numericYear <= end) values.set(numericYear, (values.get(numericYear) ?? 0) + count)
  }))
  return Array.from(values, ([year, value]) => ({ year, value }))
}

export function TrendsPage() {
  const { i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const { data, failed } = useDashboardData()
  const [countryIso, setCountryIso] = useState('ALL')
  const [rangeStart, setRangeStart] = useState(2000)

  const copy = isEnglish ? {
    kicker: 'TIME / OBSERVATIONS', title: 'Record trends', body: 'View annual record counts and coverage changes by country and start year.', all: 'All countries', country: 'Geography', range: 'Start year', observations: 'Observations in range', peak: 'Peak year', active: 'Active years', coverage: 'Country coverage', ranking: 'Country ranking', rankingNote: 'Ranked by observations inside the selected interval.', open: 'Open on map', noData: 'No observations in this interval.', failed: 'Data could not be loaded. Confirm that the local site is running, then refresh this page.', note: 'Record granularity differs by source. This chart represents record coverage, not aid amounts.', partial: 'Partial 2024 data are retained in downloads but excluded from this comparable trend line.',
  } : {
    kicker: '时间 / 观测记录', title: '记录趋势', body: '按国家和起始年份查看年度记录数量及覆盖变化。', all: '全部国家与地区', country: '地理范围', range: '起始年份', observations: '区间记录', peak: '峰值年份', active: '有记录年份', coverage: '国家覆盖', ranking: '国家排名', rankingNote: '按所选时间区间内的记录数量排序。', open: '在地图中打开', noData: '该区间暂无记录。', failed: '数据加载失败，请确认本地网站已启动后刷新页面。', note: '不同数据源的记录颗粒度不同，本图表示记录覆盖，不表示援助金额。', partial: '下载文件保留2024年部分数据；可比趋势线暂不纳入该年。',
  }

  const countries = useMemo(() => Object.values(data?.countries ?? {}).sort((a, b) => (isEnglish ? a.nameEn.localeCompare(b.nameEn) : a.nameZh.localeCompare(b.nameZh, 'zh-CN'))), [data, isEnglish])
  const selectedCountries = countryIso === 'ALL' ? countries : countries.filter((country) => country.iso3 === countryIso)
  const endYear = data?.global.trendComparisonYearMax ?? data?.global.yearMax ?? 2023
  const series = useMemo(() => buildSeries(selectedCountries, rangeStart, endYear), [selectedCountries, rangeStart, endYear])
  const maximum = Math.max(1, ...series.map((item) => item.value))
  const total = series.reduce((sum, item) => sum + item.value, 0)
  const peak = series.reduce((best, item) => item.value > best.value ? item : best, { year: rangeStart, value: 0 })
  const activeYears = series.filter((item) => item.value > 0).length
  const coveredCountries = selectedCountries.filter((country) => recordsInRange(country, rangeStart, endYear) > 0).length
  const ranked = countries.map((country) => ({ country, value: recordsInRange(country, rangeStart, endYear) })).filter((item) => item.value > 0).sort((a, b) => b.value - a.value).slice(0, 10)
  const linePoints = series.map((item, index) => `${series.length === 1 ? 0 : (index / (series.length - 1)) * 100},${94 - (item.value / maximum) * 82}`).join(' ')
  const areaPoints = `0,94 ${linePoints} 100,94`

  if (failed) return <main id="main-content" className="analytics-state">{copy.failed}</main>

  return (
    <main id="main-content" className="analytics-page trends-page">
      <header className="analytics-hero">
        <span>{copy.kicker}</span>
        <h1>{copy.title}</h1>
        <p>{copy.body}</p>
      </header>

      <section className="analytics-controls" aria-label={isEnglish ? 'Trend filters' : '趋势筛选'}>
        <label><span>{copy.country}</span><select value={countryIso} onChange={(event) => setCountryIso(event.target.value)}><option value="ALL">{copy.all}</option>{countries.map((country) => <option key={country.iso3} value={country.iso3}>{isEnglish ? country.nameEn : country.nameZh}</option>)}</select></label>
        <div className="range-control"><span>{copy.range}</span><div>{rangeStarts.map((year) => <button key={year} className={rangeStart === year ? 'active' : ''} onClick={() => setRangeStart(year)}>{year}</button>)}</div></div>
      </section>

      <section className="trend-workbench">
        <div className="trend-summary">
          <article><span>{copy.observations}</span><strong>{compactNumber(total)}</strong></article>
          <article><span>{copy.peak}</span><strong>{peak.value ? peak.year : '—'}</strong><small>{peak.value ? numberFormatter.format(peak.value) : ''}</small></article>
          <article><span>{copy.active}</span><strong>{activeYears}</strong><small>/{series.length}</small></article>
          <article><span>{copy.coverage}</span><strong>{coveredCountries}</strong><small>/{countryIso === 'ALL' ? countries.length : 1}</small></article>
        </div>
        <div className="trend-chart" role="img" aria-label={`${copy.observations}: ${numberFormatter.format(total)}`}>
          <div className="chart-grid" aria-hidden="true"><i /><i /><i /><i /></div>
          {total ? <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#4de3ad" stopOpacity=".34" /><stop offset="1" stopColor="#4de3ad" stopOpacity="0" /></linearGradient></defs><polygon points={areaPoints} fill="url(#trend-fill)" /><polyline points={linePoints} /></svg> : <div className="chart-empty">{copy.noData}</div>}
          <div className="chart-axis"><span>{rangeStart}</span><span>{Math.round((rangeStart + endYear) / 2)}</span><span>{endYear}</span></div>
        </div>
        <aside className="trend-note"><span>{copy.note}</span>{data?.global.latestYearCoverage === 'partial' && <b>{copy.partial}</b>}</aside>
      </section>

      <section className="ranking-section">
        <header><span>RANK / 10</span><h2>{copy.ranking}</h2><p>{copy.rankingNote}</p></header>
        <ol className="country-ranking">{ranked.map(({ country, value }, index) => <li key={country.iso3}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{isEnglish ? country.nameEn : country.nameZh}</strong><small>{country.iso3} · {country.sourceCount}/12</small></div><i><b style={{ width: `${(value / (ranked[0]?.value ?? 1)) * 100}%` }} /></i><em>{compactNumber(value)}</em><Link to={`/?country=${country.iso3}`}>{copy.open} ↗</Link></li>)}</ol>
      </section>
    </main>
  )
}
