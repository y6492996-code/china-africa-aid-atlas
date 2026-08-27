import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface SourceFinding { id: string; label: string; category: string; unit: string; priceBasis: string; measure: string; observedCount: number; missingRate: number; countries: number; years: number; median: number | string; peakYear: number | null; peakValue: number | null; topCountry: string | null; topCountryIso3: string | null; topCountryValue: number | null }
interface CorrelationFinding { scope: string; left_metric: string; left_label: string; right_metric: string; right_label: string; paired_observations: number; shared_country_years: number; spearman_rho: number; kendall_tau_b: number; comparability_tier: string }
interface BreakpointFinding { metric_id: string; metric_label: string; series_variant: string; break_number: number; break_year: number; pre_mean_original: number; post_mean_original: number; relative_change: number | string; bic_improvement: number; evidence_strength: string; unit: string; price_basis: string }
interface RobustnessFinding { scope: string; left_metric: string; right_metric: string; lineage_classification: string; baseline_n: number; robust_n: number; baseline_spearman: number; robust_spearman: number; delta_spearman: number; flagged_outliers_removed: number; stability: string }
interface EmpiricalReport { generatedAt: string; method: Record<string, string>; summary: { metricsProfiled: number; annualRows: number; countrySummaryRows: number; correlationRows: number; breakModels: number; breakpoints: number; robustnessRows: number; outlierCandidatesExcludedInSensitivity: number }; sources: SourceFinding[]; correlations: CorrelationFinding[]; breakpoints: BreakpointFinding[]; robustness: RobustnessFinding[] }

const categoryOrder = ['all', 'project_finance', 'debt', 'investment', 'health', 'energy', 'trade_proxy']

function compactNumber(value: number | string | null, locale: string) {
  if (value === null || value === '') return '—'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 }).format(numeric)
}

export function FindingsPage() {
  const { i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const locale = isEnglish ? 'en-US' : 'zh-CN'
  const [report, setReport] = useState<EmpiricalReport | null>(null)
  const [category, setCategory] = useState('all')
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/generated/empirical_report.json`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('report unavailable')))
      .then(setReport).catch(() => undefined)
    return () => controller.abort()
  }, [])
  const visibleSources = useMemo(() => report?.sources.filter((source) => category === 'all' || source.category === category) ?? [], [category, report])
  const strongest = report?.correlations[0]
  const copy = isEnglish ? {
    kicker: 'ANALYSIS / RESULTS', title: 'Analysis results', body: 'Review descriptive statistics, cross-source correlations, structural changes and robustness checks.',
    metrics: 'metrics profiled', annual: 'candidate breaks', correlations: 'robustness checks', strongest: 'Strongest observed rank association', rho: 'Spearman ρ', tau: 'Kendall τ-b', pairs: 'paired units',
    lineage: 'A high coefficient can reflect shared database lineage, source coverage or duplicated records. It is not proof of monetary agreement or causal evidence.',
    sourceSection: 'Data source statistics', sourceIntro: 'Descriptive coverage, completeness, peak year and leading country for each metric.', observed: 'observed country-years', missing: 'missing', coverage: 'coverage', peak: 'peak year', leader: 'top country', median: 'median observed value',
    correlationSection: 'Cross-source correlations', correlationIntro: 'Pairwise-complete Spearman and Kendall rank correlations.', differentBasis: 'different price bases · rank only', sameBasis: 'same price basis · rank comparison',
    breakSection: 'Structural change tests', breakIntro: 'BIC-selected mean-shift candidates in the longest consecutive annual series.', total: 'annual total', normalized: 'coverage-normalized mean', before: 'before', after: 'after',
    robustSection: 'Outlier robustness checks', robustIntro: 'Compare baseline coefficients with results after excluding flagged project-level candidates.', baseline: 'baseline', robust: 'excluding flags', delta: 'change',
    lineageLabels: { likely_shared_lineage: 'likely shared lineage', documented_cross_reference_overlap: 'cross-reference overlap', distinct_source_comparison: 'distinct-source comparison' },
    guardrails: 'Methods and interpretation notes', download: 'Result data download', get: 'Download CSV', nav: ['Overview', 'Source statistics', 'Correlations', 'Structural changes', 'Robustness', 'Downloads'], categories: { all: 'All metrics', project_finance: 'Project finance', debt: 'Debt', investment: 'Investment', health: 'Health', energy: 'Energy', trade_proxy: 'Aid exports' },
    files: [['source_descriptive_statistics.csv', 'Descriptive statistics', 'Completeness, distribution and coverage for all metrics.'], ['annual_source_trends.csv', 'Annual source trends', 'Source-year coverage and within-source totals.'], ['cross_source_correlations.csv', 'Rank correlations', 'Baseline Spearman and Kendall comparisons.'], ['structural_break_models.csv', 'Break models', 'Selected segments, candidate years and BIC diagnostics.'], ['structural_breakpoints.csv', 'Candidate breakpoints', 'Before/after means and evidence grading.'], ['correlation_robustness.csv', 'Robustness checks', 'Baseline versus outlier-excluded coefficients and lineage flags.']],
  } : {
    kicker: '分析 / 结果', title: '分析结果', body: '查看描述统计、跨库相关性、结构变化和稳健性检验结果。',
    metrics: '个指标完成画像', annual: '个结构变化候选', correlations: '组稳健性检验', strongest: '当前最强的排序关联', rho: 'Spearman ρ', tau: 'Kendall τ-b', pairs: '个配对单元',
    lineage: '较高的相关系数可能来自数据库谱系、覆盖范围或重复收录，不能视为金额一致性的证明，更不是因果证据。',
    sourceSection: '数据源统计概览', sourceIntro: '查看各指标的覆盖、完整率、峰值年份和首位国家。', observed: '个国家—年度观测', missing: '缺失', coverage: '覆盖', peak: '峰值年份', leader: '首位国家', median: '观测中位数',
    correlationSection: '跨库相关性', correlationIntro: '使用成对完整观测计算Spearman与Kendall秩相关系数。', differentBasis: '价格基期不同 · 仅比较秩', sameBasis: '价格基期相同 · 秩比较',
    breakSection: '结构变化检验', breakIntro: '在最长连续年度区间内识别由BIC选择的均值变化候选点。', total: '年度总量', normalized: '覆盖标准化均值', before: '变化前', after: '变化后',
    robustSection: '异常值稳健性检验', robustIntro: '比较基准结果与剔除项目级异常候选后的相关系数。', baseline: '基准', robust: '剔除后', delta: '变化量',
    lineageLabels: { likely_shared_lineage: '疑似同源', documented_cross_reference_overlap: '存在交叉引用', distinct_source_comparison: '不同来源比较' },
    guardrails: '方法与解释说明', download: '结果数据下载', get: '下载 CSV', nav: ['概览', '数据源统计', '相关性', '结构变化', '稳健性', '结果下载'], categories: { all: '全部指标', project_finance: '项目融资', debt: '债务', investment: '投资', health: '卫生', energy: '能源', trade_proxy: '援助出口' },
    files: [['source_descriptive_statistics.csv', '逐来源描述统计', '全部指标的完整性、分布和覆盖范围。'], ['annual_source_trends.csv', '年度来源趋势', '逐来源—年度覆盖和来源内总量。'], ['cross_source_correlations.csv', '秩相关结果', '基准Spearman与Kendall比较。'], ['structural_break_models.csv', '结构变化模型', '入选分段、候选年份和BIC诊断。'], ['structural_breakpoints.csv', '结构变化候选点', '变化前后均值与证据等级。'], ['correlation_robustness.csv', '稳健性检验', '基准与剔除异常值后的系数及谱系标记。']],
  }
  return <main id="main-content" className="findings-page">
    <header id="analysis-overview" className="findings-hero"><span>{copy.kicker}</span><h1>{copy.title}</h1><p>{copy.body}</p><div className="findings-kpis"><div><strong>{report?.summary.metricsProfiled ?? 14}</strong><span>{copy.metrics}</span></div><div><strong>{report?.summary.breakpoints ?? '—'}</strong><span>{copy.annual}</span></div><div><strong>{report?.summary.robustnessRows ?? '—'}</strong><span>{copy.correlations}</span></div></div></header>
    <nav className="findings-subnav" aria-label={isEnglish ? 'Analysis sections' : '分析结果页内导航'}>{[['analysis-overview', copy.nav[0]], ['source-statistics', copy.nav[1]], ['correlations', copy.nav[2]], ['structural-changes', copy.nav[3]], ['robustness', copy.nav[4]], ['result-downloads', copy.nav[5]]].map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav>
    {strongest && <section className="strongest-finding"><span>01 / ASSOCIATION</span><div><small>{copy.strongest}</small><h2>{strongest.left_label}<i>×</i>{strongest.right_label}</h2><p>{copy.lineage}</p></div><dl><div><dt>{copy.rho}</dt><dd>{strongest.spearman_rho.toFixed(3)}</dd></div><div><dt>{copy.tau}</dt><dd>{strongest.kendall_tau_b.toFixed(3)}</dd></div><div><dt>{copy.pairs}</dt><dd>{strongest.paired_observations}</dd></div></dl></section>}
    <section id="source-statistics" className="source-findings"><header><span>02 / SOURCES</span><h2>{copy.sourceSection}</h2><p>{copy.sourceIntro}</p></header><div className="finding-filters">{categoryOrder.map((value) => <button type="button" key={value} className={category === value ? 'active' : ''} onClick={() => setCategory(value)}>{copy.categories[value as keyof typeof copy.categories]}</button>)}</div><div className="source-finding-grid">{visibleSources.map((source) => <article key={source.id}><header><span>{source.category.replace('_', ' ')}</span><b>{source.id}</b></header><h3>{source.label}</h3><div className="source-coverage"><i><b style={{ width: `${Math.round((1 - source.missingRate) * 100)}%` }} /></i><span>{Math.round((1 - source.missingRate) * 100)}% {copy.coverage}</span></div><dl><div><dt>{copy.observed}</dt><dd>{source.observedCount.toLocaleString(locale)}</dd></div><div><dt>{copy.missing}</dt><dd>{Math.round(source.missingRate * 100)}%</dd></div><div><dt>{copy.peak}</dt><dd>{source.peakYear ?? '—'}</dd></div><div><dt>{copy.leader}</dt><dd>{source.topCountryIso3 ?? '—'}</dd></div><div><dt>{copy.median}</dt><dd>{compactNumber(source.median, locale)} <small>{source.unit}</small></dd></div></dl><footer>{source.priceBasis}<span>{source.measure}</span></footer></article>)}</div></section>
    <section id="correlations" className="correlation-findings"><header><span>03 / RANKS</span><h2>{copy.correlationSection}</h2><p>{copy.correlationIntro}</p></header><div>{report?.correlations.slice(0, 10).map((row, index) => <article key={`${row.scope}-${row.left_metric}-${row.right_metric}`}><b>{String(index + 1).padStart(2, '0')}</b><div><h3>{row.left_metric}<i>×</i>{row.right_metric}</h3><span>{row.scope.replaceAll('_', ' ')}</span></div><dl><div><dt>ρ</dt><dd>{row.spearman_rho.toFixed(3)}</dd></div><div><dt>τ-b</dt><dd>{row.kendall_tau_b.toFixed(3)}</dd></div><div><dt>N</dt><dd>{row.paired_observations}</dd></div></dl><em>{row.comparability_tier === 'different_basis_rank_only' ? copy.differentBasis : copy.sameBasis}</em></article>)}</div></section>
    <section id="structural-changes" className="break-findings"><header><span>04 / BREAKS</span><h2>{copy.breakSection}</h2><p>{copy.breakIntro}</p></header><div>{report?.breakpoints.slice(0, 8).map((row) => <article key={`${row.metric_id}-${row.series_variant}-${row.break_number}`}><span>{row.break_year}</span><div><h3>{row.metric_label}</h3><small>{row.series_variant === 'annual_total' ? copy.total : copy.normalized} · {row.evidence_strength}</small></div><dl><div><dt>{copy.before}</dt><dd>{compactNumber(row.pre_mean_original, locale)}</dd></div><div><dt>{copy.after}</dt><dd>{compactNumber(row.post_mean_original, locale)}</dd></div><div><dt>Δ</dt><dd>{row.relative_change === '' ? '—' : `${(Number(row.relative_change) * 100).toFixed(0)}%`}</dd></div></dl></article>)}</div></section>
    <section id="robustness" className="robust-findings"><header><span>05 / ROBUSTNESS</span><h2>{copy.robustSection}</h2><p>{copy.robustIntro}</p></header><div>{report?.robustness.slice(0, 10).map((row) => <article key={`${row.scope}-${row.left_metric}-${row.right_metric}`}><div><h3>{row.left_metric}<i>×</i>{row.right_metric}</h3><span>{copy.lineageLabels[row.lineage_classification as keyof typeof copy.lineageLabels]}</span></div><dl><div><dt>{copy.baseline}</dt><dd>{row.baseline_spearman.toFixed(3)}</dd></div><div><dt>{copy.robust}</dt><dd>{row.robust_spearman.toFixed(3)}</dd></div><div><dt>{copy.delta}</dt><dd>{row.delta_spearman >= 0 ? '+' : ''}{row.delta_spearman.toFixed(3)}</dd></div></dl><em>{row.stability.replaceAll('_', ' ')} · N {row.baseline_n}→{row.robust_n}</em></article>)}</div></section>
    <section className="finding-method"><header><span>06 / LIMITS</span><h2>{copy.guardrails}</h2></header><div>{report && Object.values(report.method).map((item, index) => <p key={item}><b>{String(index + 1).padStart(2, '0')}</b>{item}</p>)}</div></section>
    <section id="result-downloads" className="finding-downloads"><header><span>07 / DATA</span><h2>{copy.download}</h2></header><div>{copy.files.map(([file, title, body]) => <article key={file}><span>CSV</span><h3>{title}</h3><p>{body}</p><a href={`${import.meta.env.BASE_URL}data/generated/${file}`} download>{copy.get}<b>→</b></a></article>)}</div></section>
  </main>
}
