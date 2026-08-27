import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { sourceRegistry, type SourceCategory } from '../data/sourceRegistry'

const categoryLabels: Record<'all' | SourceCategory, { zh: string; en: string }> = {
  all: { zh: '全部', en: 'All' },
  aid: { zh: '援助', en: 'Aid' },
  finance: { zh: '发展融资', en: 'Finance' },
  debt: { zh: '债务', en: 'Debt' },
  investment: { zh: '投资', en: 'Investment' },
  energy: { zh: '能源', en: 'Energy' },
  health: { zh: '卫生', en: 'Health' },
}

const categories = Object.keys(categoryLabels) as Array<'all' | SourceCategory>

function formatRecords(value: number, locale: string) {
  return new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'zh-CN').format(value)
}

export function DatabasesPage() {
  const { t, i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const copy = isEnglish ? {
    kicker: 'DATABASE INDEX / 12 SOURCES',
    title: 'Data source catalogue',
    intro: 'Review coverage, observation level, time span, amount basis and available fields across 12 data sources.',
    search: 'Search databases, topics or measurement units',
    records: 'records in current view', countries: 'maximum country coverage', span: 'combined time window', sources: 'sources available',
    compare: 'Comparison workspace', selected: 'selected', hint: 'Select 2–4 databases below', clear: 'Clear',
    volume: 'Record volume', coverage: 'Country coverage', duration: 'Time span',
    catalogue: 'All data sources', catalogueIntro: 'Open a source card to review its coverage, measurement basis and cleaned files.',
    add: 'Add to comparison', remove: 'Selected', files: 'clean files', basis: 'measurement', empty: 'No database matches the current filters.',
    note: 'Record volume uses a logarithmic visual scale so that smaller project databases remain legible beside IHME.',
  } : {
    kicker: 'DATABASE INDEX / 12 SOURCES',
    title: '数据源目录',
    intro: '查看12个数据源的覆盖范围、记录层级、时间跨度、金额口径和可用字段。',
    search: '搜索数据库、主题或计量口径',
    records: '当前视图记录数', countries: '最大国家覆盖', span: '合并时间窗口', sources: '可用数据源',
    compare: '数据源对比', selected: '已选择', hint: '从下方选择 2–4 个数据源', clear: '清空',
    volume: '记录规模', coverage: '国家覆盖', duration: '时间跨度',
    catalogue: '全部数据源', catalogueIntro: '查看各数据源的覆盖范围、计量口径和清洗文件。',
    add: '加入比较', remove: '已选择', files: '清洗文件', basis: '计量口径', empty: '没有符合当前筛选条件的数据库。',
    note: '记录规模采用对数视觉尺度，使项目型小数据库与 IHME 同屏时仍然可读。',
  }

  const [category, setCategory] = useState<'all' | SourceCategory>('all')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string[]>(['aiddata', 'cla', 'ihme'])

  const filteredSources = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return sourceRegistry.filter((source) => {
      const matchesCategory = category === 'all' || source.category === category
      const haystack = `${source.name} ${source.shortName} ${source.level} ${source.amountBasis} ${source.description}`.toLocaleLowerCase()
      return matchesCategory && (!needle || haystack.includes(needle))
    })
  }, [category, query])

  const selectedSources = selected.map((id) => sourceRegistry.find((source) => source.id === id)).filter(Boolean) as typeof sourceRegistry
  const totalRecords = filteredSources.reduce((sum, source) => sum + source.records, 0)
  const maxCountries = Math.max(0, ...filteredSources.map((source) => source.countries))
  const startYear = Math.min(...filteredSources.map((source) => source.startYear))
  const endYear = Math.max(...filteredSources.map((source) => source.endYear))

  const toggleSource = (id: string) => {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id)
      if (current.length >= 4) return [...current.slice(1), id]
      return [...current, id]
    })
  }

  return (
    <main id="main-content" className="database-page">
      <header className="database-hero">
        <div className="database-hero-copy">
          <p className="database-kicker">{copy.kicker}</p>
          <h1>{copy.title}</h1>
          <p>{copy.intro}</p>
        </div>
        <div className="database-hero-geometry" aria-hidden="true"><i /><i /><i /><i /></div>
      </header>

      <section className="database-toolbar" aria-label={t('pages.databases.title')}>
        <label className="database-search">
          <span aria-hidden="true">⌕</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={copy.search} />
        </label>
        <div className="category-filter" role="group" aria-label={isEnglish ? 'Filter by category' : '按类别筛选'}>
          {categories.map((item) => (
            <button key={item} type="button" className={category === item ? 'active' : ''} onClick={() => setCategory(item)}>
              {categoryLabels[item][isEnglish ? 'en' : 'zh']}
            </button>
          ))}
        </div>
      </section>

      <section className="database-kpis" aria-label={isEnglish ? 'Current filter summary' : '当前筛选概况'}>
        <div><strong>{formatRecords(totalRecords, i18n.resolvedLanguage ?? 'zh')}</strong><span>{copy.records}</span></div>
        <div><strong>{maxCountries || '—'}</strong><span>{copy.countries}</span></div>
        <div><strong>{Number.isFinite(startYear) ? `${startYear}—${endYear}` : '—'}</strong><span>{copy.span}</span></div>
        <div><strong>{filteredSources.length}/12</strong><span>{copy.sources}</span></div>
      </section>

      <section className="compare-workbench">
        <div className="compare-heading">
          <div><span>01 / COMPARE</span><h2>{copy.compare}</h2><p>{selected.length ? `${selected.length} ${copy.selected}` : copy.hint}</p></div>
          <button type="button" onClick={() => setSelected([])} disabled={!selected.length}>{copy.clear}</button>
        </div>
        {selectedSources.length ? (
          <div className="comparison-grid">
            {selectedSources.map((source) => {
              const duration = source.endYear - source.startYear + 1
              return (
                <article className="comparison-column" key={source.id}>
                  <div className="comparison-source"><i className={`source-dot ${source.category}`} /><b>{source.shortName}</b><span>{source.level}</span></div>
                  <div className="comparison-measure"><span>{copy.volume}</span><strong>{formatRecords(source.records, i18n.resolvedLanguage ?? 'zh')}</strong><i style={{ width: `${Math.max(8, (Math.log10(source.records) / Math.log10(300444)) * 100)}%` }} /></div>
                  <div className="comparison-measure"><span>{copy.coverage}</span><strong>{source.countries}</strong><i style={{ width: `${(source.countries / 56) * 100}%` }} /></div>
                  <div className="comparison-measure"><span>{copy.duration}</span><strong>{source.startYear}—{source.endYear}</strong><i style={{ width: `${Math.min(100, (duration / 64) * 100)}%` }} /></div>
                  <p>{source.amountBasis}</p>
                </article>
              )
            })}
          </div>
        ) : <div className="comparison-empty">{copy.hint}</div>}
        <p className="comparison-note">{copy.note}</p>
      </section>

      <section className="database-catalogue">
        <div className="catalogue-heading"><span>02 / CATALOGUE</span><h2>{copy.catalogue}</h2><p>{copy.catalogueIntro}</p></div>
        <div className="source-card-grid">
          {filteredSources.map((source) => {
            const isSelected = selected.includes(source.id)
            return (
              <article className={`source-card ${isSelected ? 'selected' : ''}`} key={source.id}>
                <div className="source-card-top"><i className={`source-dot ${source.category}`} /><span>{categoryLabels[source.category][isEnglish ? 'en' : 'zh']}</span><b>{source.status === 'available' ? '● LIVE' : source.status}</b></div>
                <h3>{source.shortName}</h3>
                <h4>{source.name}</h4>
                <p>{source.description}</p>
                <dl>
                  <div><dt>{copy.volume}</dt><dd>{formatRecords(source.records, i18n.resolvedLanguage ?? 'zh')}</dd></div>
                  <div><dt>{copy.coverage}</dt><dd>{source.countries}</dd></div>
                  <div><dt>{copy.duration}</dt><dd>{source.startYear}—{source.endYear}</dd></div>
                  <div><dt>{copy.files}</dt><dd>{source.files.length}</dd></div>
                </dl>
                <div className="source-basis"><span>{copy.basis}</span><strong>{source.amountBasis}</strong></div>
                <button type="button" aria-pressed={isSelected} onClick={() => toggleSource(source.id)}>{isSelected ? `✓ ${copy.remove}` : `＋ ${copy.add}`}</button>
              </article>
            )
          })}
        </div>
        {!filteredSources.length && <div className="database-empty">{copy.empty}</div>}
      </section>
    </main>
  )
}
