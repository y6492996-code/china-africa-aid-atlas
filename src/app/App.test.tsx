import { fireEvent, render, screen } from '@testing-library/react'
import { HashRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import App from './App'

const dashboard = {
  generatedAt: '2026-08-03T00:00:00Z',
  global: { sourceCount: 12, countryCount: 55, recordCount: 322009, yearMin: 1967, yearMax: 2024, trendComparisonYearMax: 2023, latestYearCoverage: 'partial' },
  sources: [{ id: 'aiddata', label: 'AidData', rows: 10, mappedRows: 10, mappedRate: 1, metricKnownRate: 1, yearMin: 2000, yearMax: 2023, columns: [{ file: 'aiddata.csv', fields: ['country', 'year'] }] }],
  countries: {
    ETH: { iso3: 'ETH', nameEn: 'Ethiopia', nameZh: '埃塞俄比亚', records: 120, sourceCount: 8, sourceCounts: { aiddata: 120 }, yearMin: 2000, yearMax: 2023, yearCounts: { '2000': 20, '2023': 100 }, metrics: { aiddata: { value: 1000000, known: 5, label: '项目承诺金额', unit: 'USD' } } },
    AGO: { iso3: 'AGO', nameEn: 'Angola', nameZh: '安哥拉', records: 90, sourceCount: 7, sourceCounts: { aiddata: 90 }, yearMin: 2001, yearMax: 2022, yearCounts: { '2001': 30, '2022': 60 }, metrics: {} },
  },
}

const geo = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { iso3: 'ETH', name: 'Ethiopia' }, geometry: { type: 'Polygon', coordinates: [[[35, 14], [48, 14], [48, 4], [35, 4], [35, 14]]] } },
    { type: 'Feature', properties: { iso3: 'AGO', name: 'Angola' }, geometry: { type: 'Polygon', coordinates: [[[12, -4], [24, -4], [24, -18], [12, -18], [12, -4]]] } },
  ],
}

const reviewQueue = {
  appliedReviewCount: 0,
  rows: [{
    candidate_id: 'MC-1', country_iso3: 'GHA', year: 2012, similarity: 0.84,
    review_hint: 'qualifier_conflict_check_separate_projects',
    suggested_decision: 'different_project', suggestion_confidence: 'high',
    suggestion_reason: 'Conflicting loan identifiers.',
    left_source: 'codf', left_record_id: 'GH.022', left_title: 'Bui Hydropower Project Loan 1',
    left_amount_value: 100000000, left_price_basis: 'nominal_usd', left_fund_type: 'loan', left_sector: 'energy',
    right_source: 'cla', right_record_id: 'GH.066', right_title: 'Bui Hydropower Project Loan 2',
    right_amount_value: 200000000, right_price_basis: 'nominal_usd', right_fund_type: 'loan', right_sector: 'energy',
    amount_ratio_if_comparable: 0.5,
  }],
}

const empiricalReport = {
  generatedAt: '2026-08-04T00:00:00Z',
  method: { panel: '54 countries', missing: 'Pairwise complete observations.', correlation: 'Rank correlations.', aggregation: 'Within source only.', causality: 'Descriptive only.' },
  summary: { metricsProfiled: 14, annualRows: 350, countrySummaryRows: 598, correlationRows: 30, breakModels: 24, breakpoints: 18, robustnessRows: 30, outlierCandidatesExcludedInSensitivity: 8 },
  sources: [{ id: 'codf', label: 'CODF loan commitments', category: 'project_finance', unit: 'USD', priceBasis: 'nominal_usd', measure: 'loan_commitment', observedCount: 252, missingRate: .81, countries: 44, years: 17, median: 200830000, peakYear: 2016, peakValue: 22812360000, topCountry: 'Angola', topCountryIso3: 'AGO', topCountryValue: 33173880000 }],
  correlations: [{ scope: 'country_common_year_total', left_metric: 'codf', left_label: 'CODF loan commitments', right_metric: 'cla', right_label: 'CLA loan commitments', paired_observations: 38, shared_country_years: 234, spearman_rho: .97352, kendall_tau_b: .894737, comparability_tier: 'same_basis_rank_comparison' }],
  breakpoints: [{ metric_id: 'codf', metric_label: 'CODF loan commitments', series_variant: 'annual_total', break_number: 1, break_year: 2013, pre_mean_original: 100, post_mean_original: 180, relative_change: .8, bic_improvement: 12, evidence_strength: 'strong', unit: 'USD', price_basis: 'nominal_usd' }],
  robustness: [{ scope: 'country_common_year_total', left_metric: 'codf', right_metric: 'cla', lineage_classification: 'likely_shared_lineage', baseline_n: 38, robust_n: 38, baseline_spearman: .97352, robust_spearman: .965, delta_spearman: -.00852, flagged_outliers_removed: 8, stability: 'stable' }],
}

describe('Atlas application shell', () => {
  beforeEach(async () => {
    window.localStorage.clear()
    window.location.hash = '#/'
    await i18n.changeLanguage('zh')
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
      ok: true,
      json: async () => String(input).includes('match_review_queue.json') ? reviewQueue : String(input).includes('empirical_report.json') ? empiricalReport : String(input).includes('dashboard.json') ? dashboard : geo,
    } as Response)))
  })

  it('renders the map-first home page and switches countries', async () => {
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('中非援助')
    expect((await screen.findAllByRole('heading', { name: '埃塞俄比亚' })).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /安哥拉/ }))
    expect((await screen.findAllByRole('heading', { name: '安哥拉' })).length).toBeGreaterThan(0)
  })

  it('switches the map interface to English', async () => {
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    fireEvent.click(await screen.findByRole('button', { name: /English/i }))
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('China–Africa Aid')
  })

  it('filters the database catalogue and updates the comparison', async () => {
    window.location.hash = '#/databases'
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    const search = await screen.findByRole('textbox')
    fireEvent.change(search, { target: { value: 'IHME' } })
    expect(screen.getAllByText('IHME DAH').length).toBeGreaterThan(0)
  })

  it('renders the trend workbench with country observations', async () => {
    window.location.hash = '#/trends'
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    expect(await screen.findByRole('heading', { name: '记录趋势' })).toBeInTheDocument()
    expect(screen.getByText('210')).toBeInTheDocument()
  })

  it('filters the country directory and links back to the map', async () => {
    window.location.hash = '#/countries'
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    const search = await screen.findByRole('textbox', { name: '搜索国家或ISO代码' })
    fireEvent.change(search, { target: { value: 'AGO' } })
    expect(screen.getByRole('heading', { name: '安哥拉' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '埃塞俄比亚' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /打开地图/ })).toHaveAttribute('href', '#/?country=AGO')
  })

  it('opens the match review workbench and records a decision locally', async () => {
    window.location.hash = '#/review'
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    expect(await screen.findByRole('heading', { name: '项目匹配审核' })).toBeInTheDocument()
    expect(screen.getByText('Bui Hydropower Project Loan 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '将当前候选标记为：不同项目' }))
    expect(JSON.parse(window.localStorage.getItem('caad-match-review-v1') || '{}')['MC-1'].decision).toBe('different_project')
  })

  it('renders empirical findings without combining source totals', async () => {
    window.location.hash = '#/findings'
    render(<HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></HashRouter>)
    expect(await screen.findByRole('heading', { name: '分析结果' })).toBeInTheDocument()
    expect(screen.getAllByText('CODF loan commitments').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.974').length).toBeGreaterThan(0)
    expect(screen.getByText('2013')).toBeInTheDocument()
    expect(screen.getByText('疑似同源')).toBeInTheDocument()
  })
})
