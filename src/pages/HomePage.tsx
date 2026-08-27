import { useEffect, useMemo, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

type MapMode = 'coverage' | 'records'

interface CountryMetric { value: number; known: number; label: string; unit: string }
interface CountryData {
  iso3: string; nameEn: string; nameZh: string; records: number; sourceCount: number
  sourceCounts: Record<string, number>; yearMin: number | null; yearMax: number | null
  yearCounts: Record<string, number>; metrics: Record<string, CountryMetric>
}
interface SourceData {
  id: string; label: string; rows: number; mappedRows: number; mappedRate: number; metricKnownRate: number
  yearMin: number | null; yearMax: number | null; columns: Array<{ file: string; fields: string[] }>
}
interface DashboardData {
  generatedAt: string
  global: { sourceCount: number; countryCount: number; recordCount: number; yearMin: number; yearMax: number; trendComparisonYearMax: number; latestYearCoverage: 'partial' | 'observed' }
  sources: SourceData[]; countries: Record<string, CountryData>
}
interface GeoFeature {
  type: 'Feature'; properties: { iso3: string; name: string }
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] }
}
interface GeoCollection { type: 'FeatureCollection'; features: GeoFeature[] }

const numberFormatter = new Intl.NumberFormat('en-US')

function projectPoint(point: number[]) { return [(point[0] + 20) * 9.15, (38 - point[1]) * 9.15] }
function ringToPath(ring: number[][]) {
  return ring.map((point, index) => {
    const [x, y] = projectPoint(point)
    return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ') + ' Z'
}
function featureToPath(feature: GeoFeature) {
  if (!feature.geometry) return ''
  if (feature.geometry.type === 'Polygon') return (feature.geometry.coordinates as number[][][]).map(ringToPath).join(' ')
  return (feature.geometry.coordinates as number[][][][]).flatMap((polygon) => polygon.map(ringToPath)).join(' ')
}
function mapColor(country: CountryData | undefined, mode: MapMode, maxRecords: number) {
  if (!country) return '#131820'
  const strength = mode === 'coverage' ? country.sourceCount / 12 : Math.log10(country.records + 1) / Math.log10(maxRecords + 1)
  return `hsl(157 72% ${18 + strength * 46}%)`
}
function compactNumber(value: number) {
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`
  if (absolute >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (absolute >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return numberFormatter.format(Math.round(value))
}
function metricValue(metric: CountryMetric) {
  if (metric.unit.endsWith('USD')) return `$${compactNumber(metric.value)}`
  if (metric.unit.includes('million')) return `${compactNumber(metric.value)}m`
  if (metric.unit === 'MW') return `${compactNumber(metric.value)} MW`
  return compactNumber(metric.value)
}

function TrendLine({ country, comparisonEndYear }: { country: CountryData; comparisonEndYear: number }) {
  const years = Object.keys(country.yearCounts).map(Number).sort((a, b) => a - b)
  if (!years.length) return <div className="trend-empty">—</div>
  const start = Math.max(1990, years[0])
  const end = Math.min(comparisonEndYear, years[years.length - 1])
  const series = Array.from({ length: Math.max(1, end - start + 1) }, (_, index) => ({ year: start + index, value: country.yearCounts[String(start + index)] ?? 0 }))
  const maximum = Math.max(1, ...series.map((item) => item.value))
  const points = series.map((item, index) => {
    const x = series.length === 1 ? 0 : (index / (series.length - 1)) * 100
    return `${x.toFixed(2)},${(42 - (item.value / maximum) * 38).toFixed(2)}`
  }).join(' ')
  return <div className="country-trend" aria-label={`${country.nameEn} yearly record trend`}><svg viewBox="0 0 100 46" preserveAspectRatio="none" role="img"><line x1="0" y1="42" x2="100" y2="42" /><polyline points={points} /></svg><div><span>{start}</span><span>{end}</span></div></div>
}

export function HomePage() {
  const { i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [geo, setGeo] = useState<GeoCollection | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedIso, setSelectedIso] = useState(() => searchParams.get('country')?.toUpperCase() || 'ETH')
  const [hoveredIso, setHoveredIso] = useState<string | null>(null)
  const [mapMode, setMapMode] = useState<MapMode>('coverage')
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const base = import.meta.env.BASE_URL
    Promise.all([
      fetch(`${base}data/dashboard.json`, { signal: controller.signal }).then((response) => response.json()),
      fetch(`${base}data/africa.geojson`, { signal: controller.signal }).then((response) => response.json()),
    ]).then(([dashboardData, geoData]) => { setDashboard(dashboardData); setGeo(geoData) }).catch((reason) => { if (reason?.name !== 'AbortError') setError(true) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const requestedIso = searchParams.get('country')?.toUpperCase()
    if (requestedIso && dashboard?.countries[requestedIso] && requestedIso !== selectedIso) setSelectedIso(requestedIso)
  }, [dashboard, searchParams, selectedIso])

  const copy = isEnglish ? {
    title: 'China–Africa Aid Database', subtitle: 'RESEARCH OVERVIEW', coverage: 'Database coverage', records: 'Record density', countries: 'Countries', sources: 'Sources', rows: 'Mapped records', years: 'Time range', sourceMix: 'Source mix', timeline: 'Record timeline', explore: 'Data source catalogue', loading: 'Loading country data', failed: 'Data could not be loaded. Confirm that the local site is running, then refresh this page.', select: 'Select a country', fields: 'fields', mapped: 'mapped', noMetric: 'No source-specific metric', note: 'Amounts are shown under each source’s original basis.', countrySignals: 'Country indicators', sourceOverview: 'Source fields and coverage', quickTitle: 'Research tools', results: 'Analysis results', downloads: 'Data download',
  } : {
    title: '中非援助数据库', subtitle: '研究总览', coverage: '数据库覆盖', records: '记录密度', countries: '国家与地区', sources: '数据来源', rows: '可映射记录', years: '时间范围', sourceMix: '来源构成', timeline: '记录趋势', explore: '数据源目录', loading: '正在载入国家数据', failed: '数据加载失败，请确认本地网站已启动后刷新页面。', select: '选择国家', fields: '字段', mapped: '已映射', noMetric: '暂无分库指标', note: '金额按各数据源原有口径显示。', countrySignals: '国家指标', sourceOverview: '数据源字段与覆盖', quickTitle: '研究工具', results: '分析结果', downloads: '数据下载',
  }

  const country = dashboard?.countries[selectedIso]
  const hoverCountry = hoveredIso ? dashboard?.countries[hoveredIso] : undefined
  const sourceLabels = useMemo(() => Object.fromEntries((dashboard?.sources ?? []).map((source) => [source.id, source.label])), [dashboard])
  const countries = useMemo(() => Object.values(dashboard?.countries ?? {}).sort((a, b) => (isEnglish ? a.nameEn.localeCompare(b.nameEn) : a.nameZh.localeCompare(b.nameZh, 'zh-CN'))), [dashboard, isEnglish])
  const maxRecords = useMemo(() => Math.max(1, ...countries.map((item) => item.records)), [countries])
  const sourceMix = country ? Object.entries(country.sourceCounts).sort((a, b) => b[1] - a[1]).slice(0, 7) : []
  const maximumSourceRecords = Math.max(1, ...sourceMix.map(([, value]) => value))
  const metrics = country ? Object.entries(country.metrics).filter(([, metric]) => metric.known > 0).sort((a, b) => b[1].known - a[1].known).slice(0, 4) : []
  const selectFeature = (iso: string) => { if (dashboard?.countries[iso]) { setSelectedIso(iso); setSearchParams({ country: iso }, { replace: true }) } }
  const onFeatureKeyDown = (event: KeyboardEvent<SVGPathElement>, iso: string) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectFeature(iso) } }

  if (error) return <main id="main-content" className="map-loading"><span>!</span><p>{copy.failed}</p></main>

  return (
    <main id="main-content" className="atlas-home">
      <section className="map-stage">
        <aside className="atlas-rail">
          <div className="atlas-title"><span>{copy.subtitle}</span><h1>{copy.title}</h1></div>
          {dashboard ? <dl className="global-stats"><div><dt>{copy.countries}</dt><dd>{dashboard.global.countryCount}</dd></div><div><dt>{copy.sources}</dt><dd>{dashboard.global.sourceCount}</dd></div><div><dt>{copy.rows}</dt><dd>{compactNumber(dashboard.global.recordCount)}</dd></div><div><dt>{copy.years}</dt><dd>{dashboard.global.yearMin}—{dashboard.global.yearMax}</dd></div></dl> : <div className="rail-loader">{copy.loading}</div>}
          <nav className="rail-quick-links" aria-label={copy.quickTitle}><span>{copy.quickTitle}</span><Link to="/databases">{copy.explore}<b>↗</b></Link><Link to="/findings">{copy.results}<b>↗</b></Link><Link to="/methods">{copy.downloads}<b>↗</b></Link></nav>
        </aside>

        <section className="africa-map-panel" aria-label={isEnglish ? 'Interactive map of Africa' : '非洲交互地图'}>
          <div className="map-controls" role="group" aria-label={isEnglish ? 'Map metric' : '地图指标'}><button className={mapMode === 'coverage' ? 'active' : ''} onClick={() => setMapMode('coverage')}>{copy.coverage}</button><button className={mapMode === 'records' ? 'active' : ''} onClick={() => setMapMode('records')}>{copy.records}</button></div>
          <div className="map-readout"><span>{hoverCountry ? (isEnglish ? hoverCountry.nameEn : hoverCountry.nameZh) : copy.select}</span><b>{hoverCountry ? `${hoverCountry.sourceCount}/12` : 'AFRICA'}</b></div>
          {geo && dashboard ? <svg className="africa-map" viewBox="0 0 690 690" role="img" aria-label={isEnglish ? 'Click a country for details' : '点击国家查看详情'}><g>{geo.features.map((feature) => {
            const iso = feature.properties.iso3
            const item = dashboard.countries[iso]
            return <path key={iso} d={featureToPath(feature)} className={`${item ? 'has-data' : 'no-data'} ${iso === selectedIso ? 'selected' : ''}`} style={{ '--map-fill': mapColor(item, mapMode, maxRecords) } as CSSProperties} role={item ? 'button' : undefined} tabIndex={item ? 0 : -1} aria-label={item ? `${isEnglish ? item.nameEn : item.nameZh}: ${item.sourceCount} / 12` : feature.properties.name} onClick={() => selectFeature(iso)} onKeyDown={(event) => onFeatureKeyDown(event, iso)} onMouseEnter={() => setHoveredIso(iso)} onMouseLeave={() => setHoveredIso(null)} />
          })}</g></svg> : <div className="map-loader"><i /><span>{copy.loading}</span></div>}
          <div className="map-scale"><span>LOW</span><i /><span>HIGH</span></div>
        </section>

        <aside className="country-panel">
          <label className="country-select"><span>{copy.select}</span><select value={selectedIso} onChange={(event) => selectFeature(event.target.value)} disabled={!dashboard}>{countries.map((item) => <option key={item.iso3} value={item.iso3}>{isEnglish ? item.nameEn : item.nameZh}</option>)}</select></label>
          {country ? <><header className="country-heading"><span>{country.iso3}</span><h2>{isEnglish ? country.nameEn : country.nameZh}</h2><p>{isEnglish ? country.nameZh : country.nameEn}</p></header><div className="country-kpis"><div><span>{copy.rows}</span><strong>{numberFormatter.format(country.records)}</strong></div><div><span>{copy.sources}</span><strong>{country.sourceCount}<small>/12</small></strong></div><div><span>{copy.years}</span><strong>{country.yearMin ?? '—'}<small>—{country.yearMax ?? '—'}</small></strong></div></div><section className="panel-block"><div className="panel-label"><span>{copy.timeline}</span><b>{dashboard.global.trendComparisonYearMax ?? dashboard.global.yearMax}</b></div><TrendLine country={country} comparisonEndYear={dashboard.global.trendComparisonYearMax ?? dashboard.global.yearMax} /></section><section className="panel-block source-mix"><div className="panel-label"><span>{copy.sourceMix}</span><b>{sourceMix.length}</b></div>{sourceMix.map(([sourceId, value]) => <div className="mix-row" key={sourceId}><span>{sourceLabels[sourceId] ?? sourceId}</span><i><b style={{ width: `${Math.max(4, (Math.log10(value + 1) / Math.log10(maximumSourceRecords + 1)) * 100)}%` }} /></i><em>{compactNumber(value)}</em></div>)}</section></> : <div className="panel-placeholder">{copy.loading}</div>}
        </aside>
      </section>

      <section className="signal-section"><header><span>COUNTRY / SIGNALS</span><h2>{copy.countrySignals}</h2><p>{country ? `${isEnglish ? country.nameEn : country.nameZh} · ${copy.note}` : copy.note}</p></header><div className="signal-grid">{metrics.length ? metrics.map(([sourceId, metric], index) => <article key={sourceId}><span>0{index + 1} · {sourceLabels[sourceId] ?? sourceId}</span><strong>{metricValue(metric)}</strong><p>{metric.label}<small>{metric.unit}</small></p></article>) : <article className="signal-empty">{copy.noMetric}</article>}</div></section>
      <section className="source-schema-section"><header><span>SOURCE / SCHEMA</span><h2>{copy.sourceOverview}</h2></header><div className="schema-list">{(dashboard?.sources ?? []).map((source) => { const fieldCount = source.columns.reduce((sum, file) => sum + file.fields.length, 0); return <Link to="/databases" key={source.id}><span>{source.label}</span><strong>{fieldCount}<small>{copy.fields}</small></strong><i><b style={{ width: `${source.mappedRate * 100}%` }} /></i><em>{Math.round(source.mappedRate * 100)}% {copy.mapped}</em></Link> })}</div></section>
    </main>
  )
}
