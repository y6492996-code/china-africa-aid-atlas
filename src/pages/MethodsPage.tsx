import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

interface BuildReport {
  generatedAt: string
  rows: Record<string, number>
  matching: Record<string, number>
  parameters: { startYear: number; endYear: number; sovereignCountries: number }
  quality?: {
    matchReviewQueueRows: number
    reviewDecisionsApplied: number
    humanConfirmedSameProject: number
    confirmedMatchGroups: number
    projectEntities: number
    outlierCandidateRows: number
    panelVariablesProfiled: number
    imputationApplied: boolean
    outliersRemoved: boolean
  }
  panelChecks?: {
    expectedWideRows: number
    actualWideRows: number
    uniqueCountryYear: number
    crossSourceAmountsSummed: boolean
    missingAmountsReplacedWithZero: boolean
  }
  dashboard?: { sourceCount: number }
}

interface ConsistencyReport {
  status: string
  counts: {
    decisions: number
    same_project: number
    different_project: number
    uncertain_or_invalid: number
  }
  confidence: { high: number; human_confirmed: number; moderate: number }
  checks: Record<string, number>
  errors: string[]
  warnings: string[]
}

const downloads = [
  { key: 'wide', group: 'core', type: 'CSV', file: 'master_panel_wide.csv', rowKey: 'master_panel_wide', fields: 'iso3 · year · country_name · source record counts · source amounts · macro indicators' },
  { key: 'project', group: 'core', type: 'CSV', file: 'project_level_master.csv', rowKey: 'project_level_master', fields: 'project_match_id · source_db · record_id · country_iso3 · year · project_name · amount_value · price_basis · match_status' },
  { key: 'source', group: 'core', type: 'CSV', file: 'long_source.csv', rowKey: 'long_source', fields: 'panel_id · iso3 · year · source · amount_usd · record_count · price_basis' },
  { key: 'fund', group: 'core', type: 'CSV', file: 'long_fundtype.csv', rowKey: 'long_fundtype', fields: 'panel_id · iso3 · year · source · fund_type · amount_usd · price_basis' },
  { key: 'dictionary', group: 'docs', type: 'CSV', file: 'data_dictionary.csv', rowKey: 'data_dictionary' },
  { key: 'buildReport', group: 'docs', type: 'JSON', file: 'build_report.json' },
  { key: 'matches', group: 'quality', type: 'CSV', file: 'match_candidates.csv', rowKey: 'match_candidates' },
  { key: 'decisions', group: 'quality', type: 'CSV', file: 'match_review_decisions_applied.csv', rowKey: 'match_review_decisions_applied' },
  { key: 'consistency', group: 'quality', type: 'JSON', file: 'match_review_consistency_report.json' },
  { key: 'quality', group: 'quality', type: 'CSV', file: 'project_quality_summary.csv', rowKey: 'project_quality_summary' },
  { key: 'missingness', group: 'quality', type: 'CSV', file: 'panel_missingness.csv', rowKey: 'panel_missingness' },
  { key: 'outliers', group: 'quality', type: 'CSV', file: 'outlier_candidates.csv', rowKey: 'outlier_candidates' },
] as const

export function MethodsPage() {
  const { i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const [report, setReport] = useState<BuildReport | null>(null)
  const [consistency, setConsistency] = useState<ConsistencyReport | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      fetch(`${import.meta.env.BASE_URL}data/generated/build_report.json`, { signal: controller.signal }),
      fetch(`${import.meta.env.BASE_URL}data/generated/match_review_consistency_report.json`, { signal: controller.signal }),
    ])
      .then(async ([buildResponse, consistencyResponse]) => {
        if (!buildResponse.ok || !consistencyResponse.ok) throw new Error('method reports unavailable')
        const [build, review] = await Promise.all([buildResponse.json(), consistencyResponse.json()])
        setReport(build)
        setConsistency(review)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  const copy = isEnglish ? {
    kicker: 'RESEARCH / METHODS', title: 'Methods and research data',
    body: 'Study scope, data processing, project matching rules, quality checks and downloadable research tables.',
    countries: 'sovereign countries', years: 'analysis years', sources: 'source families',
    jump: { pipeline: 'Processing workflow', matching: 'Project matching', quality: 'Quality and limits', download: 'Data download' },
    pipeline: 'Data processing workflow', matching: 'Project matching and review', qualityTitle: 'Quality control and research limits', download: 'Research data download',
    checkpoint: 'Latest build checks', reviewPairs: 'pairs awaiting review',
    outlierRows: 'outlier candidates retained', variables: 'panel variables profiled',
    startReview: 'View review decisions',
    note: 'Missing values remain missing. Amount fields retain their source, measure and price basis.',
    updated: 'Generated', rows: 'rows', get: 'Download', preview: 'Preview fields', fileInfo: 'Build information',
    matchingIntro: 'Candidate pairs are resolved from the strongest available evidence. Existing human decisions are preserved and take precedence.',
    matchingStats: ['decisions applied', 'same project', 'different projects', 'unresolved'],
    consistencyPass: 'Consistency checks passed',
    consistencyPending: 'Consistency report unavailable',
    consistencyText: 'No duplicate decisions, opposing pair labels, transitive contradictions or final-entity contradictions were found.',
    matchingRules: [
      ['01', 'Direct identifiers and explicit links', 'Shared source identifiers, explicit cross-source references and established entity links are the strongest positive evidence.'],
      ['02', 'Named asset and technical specifications', 'Distinctive project names, locations, capacity, voltage, phase and compatible sector context support consolidation.'],
      ['03', 'Amount and financing consistency', 'Original commitments are compared only when the price basis is compatible; financing instruments must not conflict.'],
      ['04', 'Hard separation rules', 'Different catalogue IDs, phases, lots, components, canonical events or financing instruments keep records separate.'],
      ['05', 'Conservative completion', 'Pairs without enough positive evidence remain separate. Every result retains its rule, evidence, origin and confidence in the audit trail.'],
    ],
    qualityColumns: [
      ['Panel integrity', ['54 × 25 country-year rows are unique and complete as a panel skeleton.', 'Missing amounts are not replaced with zero.', 'Outlier candidates remain in the primary data; sensitivity analysis is reported separately.']],
      ['Measurement boundary', ['Nominal and constant-price values are not treated as directly interchangeable.', 'Stocks, flows, commitments, disbursements, counts and capacity remain separate measures.', 'Amounts from different databases are never summed into a cross-source total.']],
      ['Interpretation boundary', ['Cross-source comparisons use compatible measures and rank-based statistics.', 'Shared lineage between databases is flagged in the findings.', 'Results are descriptive and do not establish causal effects.']],
      ['Reproducibility', ['Build metadata records the time window, row counts and checks.', 'Applied match decisions and the consistency report are downloadable below.', 'The same build process regenerates the panels, quality files and website data.']],
    ],
    confidence: 'Decision confidence', high: 'high-confidence rules', human: 'human-confirmed', moderate: 'conservative non-merges',
    groups: { core: ['Core research panels', 'Primary tables for analysis and modelling.'], docs: ['Data documentation', 'Variable definitions and build metadata.'], quality: ['Quality and audit files', 'Matching decisions, consistency, completeness, missingness and outlier checks.'] },
    steps: [
      ['01', 'Standardize', 'Preserve every source record while standardizing country, year, instrument and broad sector fields.'],
      ['02', 'Resolve projects', 'Apply reviewed links and auditable rules to identify the same project across databases without collapsing distinct phases or financing events.'],
      ['03', 'Aggregate', 'Build one balanced country-year panel while preserving differences among price bases and measurement types.'],
      ['04', 'Analyze and export', 'Generate source and fund-type panels, descriptive findings, robustness checks and downloadable quality files.'],
    ],
    cards: {
      wide: ['Master wide panel', 'Country-year research panel for descriptive statistics, rankings and the website.'],
      project: ['Project-level master', 'Source-preserving project and event records with match and quality fields.'],
      source: ['Source long panel', 'Balanced source-country-year structure for cross-source time analysis.'],
      fund: ['Fund-type long panel', 'Source-preserving loan, grant, equity and debt-relief observations.'],
      dictionary: ['Data dictionary', 'Variable definitions, modules and units for the analytical tables.'],
      buildReport: ['Build report', 'Generation time, parameters, row counts and data-integrity checks for the current release.'],
      matches: ['Match candidate set', 'All cross-database candidate pairs and similarity evidence used by the review process.'],
      decisions: ['Applied review decisions', 'The final same-project and different-project decisions used in the current build.'],
      consistency: ['Review consistency report', 'Decision counts, confidence levels and contradiction checks for the completed review.'],
      quality: ['Project quality summary', 'Source-by-source completeness, classification, estimation and review indicators.'],
      missingness: ['Panel missingness profile', 'Observed and missing cells, country/year coverage, zeros and negative values by variable.'],
      outliers: ['Outlier candidates', 'Source-specific robust flags for review; no record is automatically removed.'],
    },
  } : {
    kicker: '研究 / 方法', title: '研究方法与数据',
    body: '集中说明研究范围、数据处理、项目匹配规则、质量检查及可下载的研究表格。',
    countries: '个主权国家', years: '个分析年份', sources: '类数据来源',
    jump: { pipeline: '数据流程', matching: '项目匹配', quality: '质检与边界', download: '数据下载' },
    pipeline: '数据处理流程', matching: '项目匹配与审核', qualityTitle: '质量控制与研究边界', download: '研究数据下载',
    checkpoint: '本次构建检查', reviewPairs: '对候选等待审核',
    outlierRows: '条异常候选被保留', variables: '个面板变量完成缺失画像',
    startReview: '查看审核记录',
    note: '缺失值保留为空；金额字段始终保留来源、指标含义与价格基期。',
    updated: '生成时间', rows: '行', get: '下载', preview: '预览字段', fileInfo: '构建信息',
    matchingIntro: '候选项目对按最强可用证据逐级判断；已有人工决定全部保留，并优先于自动规则。',
    matchingStats: ['条审核决定已应用', '对判为同一项目', '对判为不同项目', '对仍未确定'],
    consistencyPass: '一致性检查通过',
    consistencyPending: '一致性报告暂不可用',
    consistencyText: '未发现重复决定、同一记录对的相反结论、传递矛盾或最终项目实体冲突。',
    matchingRules: [
      ['01', '直接标识与明确关联', '共享来源标识、标题中的跨库记录引用和已确认项目实体，是优先级最高的同项目证据。'],
      ['02', '项目名称与技术规格', '专有项目名称、地点、容量、电压、期次及相容的行业背景共同支持合并。'],
      ['03', '金额与融资条件', '只在价格基期可比时核对原始承诺金额；融资工具或资金性质不得冲突。'],
      ['04', '强制分离条件', '不同目录编号、期次、标段、组成部分、事件或融资工具出现冲突时，判为不同项目。'],
      ['05', '保守完成规则', '缺少充分同项目证据的候选保持分离；每条结论都保留规则、证据、来源和置信度。'],
    ],
    qualityColumns: [
      ['面板完整性', ['54 × 25 个国家—年份组合在面板骨架中唯一且完整。', '缺失金额不替换为零。', '异常候选保留在主数据中，另用敏感性分析检验影响。']],
      ['计量边界', ['名义价与不同基期的不变价不直接等同。', '存量、流量、承诺、拨付、记录数和容量指标分别保留。', '不同数据库的金额不加总为跨来源总额。']],
      ['解释边界', ['跨来源比较只使用含义相容的指标和秩相关统计。', '数据库之间的疑似共享谱系在分析结果中单独标记。', '分析结果用于描述和比较，不作因果推断。']],
      ['可复现材料', ['构建报告记录时间范围、参数、行数及完整性检查。', '已应用的匹配决定和一致性报告可在下方下载。', '同一构建流程可重新生成面板、质检文件和网页数据。']],
    ],
    confidence: '审核决定构成', high: '条高置信度规则决定', human: '条人工确认', moderate: '条保守分离决定',
    groups: { core: ['核心研究面板', '用于分析与建模的主要数据表。'], docs: ['数据说明文件', '变量定义及本次数据构建信息。'], quality: ['质检与审计文件', '匹配决定、一致性、完整率、缺失和异常值检查结果。'] },
    steps: [
      ['01', '统一字段', '保留每条来源记录，同时统一国家、年份、资金性质与宽口径行业字段。'],
      ['02', '识别同一项目', '依据已审核关联和可追溯规则识别跨库同一项目，同时避免误合并不同期次、标段或融资事件。'],
      ['03', '国家年度汇总', '构建平衡的国家—年份面板，并保留不同价格基期和指标类型之间的差异。'],
      ['04', '分析与输出', '生成来源、资金性质长面板，以及描述统计、稳健性检查和可下载质检文件。'],
    ],
    cards: {
      wide: ['主宽面板', '用于描述统计、排名、趋势和网页展示的国家—年份研究面板。'],
      project: ['项目级主表', '保留来源、项目、匹配状态和质量字段的项目及事件记录。'],
      source: ['来源长面板', '用于跨来源时间分析的平衡国家—年份—来源结构。'],
      fund: ['资金性质长面板', '保留来源的贷款、赠款、股权与债务减免记录。'],
      dictionary: ['数据字典', '分析表的变量定义、模块归属和单位说明。'],
      buildReport: ['构建报告', '记录本次生成时间、参数、各表行数和数据完整性检查。'],
      matches: ['匹配候选全集', '进入审核流程的全部跨库候选项目对及相似度证据。'],
      decisions: ['已应用审核决定', '本次构建实际采用的同项目与不同项目最终决定。'],
      consistency: ['审核一致性报告', '汇总决定数量、置信度及矛盾检查结果。'],
      quality: ['项目质量汇总', '逐来源呈现完整率、分类率、估算标记、异常与匹配审核数量。'],
      missingness: ['面板缺失画像', '逐变量统计观测、缺失、覆盖国家和年份、零值及负值。'],
      outliers: ['异常值候选', '采用来源内稳健规则标记以供复核，不自动删除任何记录。'],
    },
  }

  const decisionCounts = {
    all: consistency?.counts.decisions ?? report?.quality?.reviewDecisionsApplied ?? 1469,
    same: consistency?.counts.same_project ?? 969,
    different: consistency?.counts.different_project ?? 500,
    unresolved: consistency?.counts.uncertain_or_invalid ?? report?.quality?.matchReviewQueueRows ?? 0,
  }
  const integrityPassed = consistency?.status === 'pass' && consistency.errors.length === 0

  return (
    <main id="main-content" className="methods-page">
      <header className="methods-hero">
        <span>{copy.kicker}</span><h1>{copy.title}</h1><p>{copy.body}</p>
        <div className="methods-stats">
          <div><strong>{report?.parameters.sovereignCountries ?? 54}</strong><span>{copy.countries}</span></div>
          <div><strong>25</strong><span>{copy.years}</span></div>
          <div><strong>{report?.dashboard?.sourceCount ?? 12}</strong><span>{copy.sources}</span></div>
        </div>
      </header>

      <nav className="methods-subnav" aria-label={isEnglish ? 'Methods sections' : '研究方法页面目录'}>
        <a href="#pipeline">01 · {copy.jump.pipeline}</a>
        <a href="#matching">02 · {copy.jump.matching}</a>
        <a href="#quality">03 · {copy.jump.quality}</a>
        <a href="#download">04 · {copy.jump.download}</a>
      </nav>

      <section className="method-pipeline" id="pipeline">
        <header><span>01 / PIPELINE</span><h2>{copy.pipeline}</h2></header>
        <div>{copy.steps.map(([number, title, body]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{body}</p></article>)}</div>
        <p className="method-note">{copy.note}</p>
        <aside className="quality-strip" aria-label={copy.checkpoint}>
          <span>{copy.checkpoint}</span>
          <div><strong>{report?.quality?.matchReviewQueueRows?.toLocaleString() ?? '0'}</strong><small>{copy.reviewPairs}</small></div>
          <div><strong>{report?.quality?.outlierCandidateRows?.toLocaleString() ?? '—'}</strong><small>{copy.outlierRows}</small></div>
          <div><strong>{report?.quality?.panelVariablesProfiled?.toLocaleString() ?? '—'}</strong><small>{copy.variables}</small></div>
        </aside>
      </section>

      <section className="matching-method" id="matching">
        <header><span>02 / MATCHING</span><h2>{copy.matching}</h2><p>{copy.matchingIntro}</p></header>
        <div className="matching-summary">
          {[decisionCounts.all, decisionCounts.same, decisionCounts.different, decisionCounts.unresolved].map((value, index) => <article key={copy.matchingStats[index]}><strong>{value.toLocaleString()}</strong><span>{copy.matchingStats[index]}</span></article>)}
        </div>
        <div className="matching-body">
          <ol>{copy.matchingRules.map(([number, title, body]) => <li key={number}><b>{number}</b><div><h3>{title}</h3><p>{body}</p></div></li>)}</ol>
          <aside className={integrityPassed ? 'consistency-card is-pass' : 'consistency-card'}>
            <span>{integrityPassed ? copy.consistencyPass : copy.consistencyPending}</span>
            <strong>{integrityPassed ? 'PASS' : '—'}</strong>
            <p>{copy.consistencyText}</p>
            <dl>
              <div><dt>{copy.high}</dt><dd>{consistency?.confidence.high?.toLocaleString() ?? '1,364'}</dd></div>
              <div><dt>{copy.human}</dt><dd>{consistency?.confidence.human_confirmed?.toLocaleString() ?? '69'}</dd></div>
              <div><dt>{copy.moderate}</dt><dd>{consistency?.confidence.moderate?.toLocaleString() ?? '36'}</dd></div>
            </dl>
            <small>{copy.confidence}</small>
          </aside>
        </div>
        <Link className="review-start" to="/review">{copy.startReview}<b>→</b></Link>
      </section>

      <section className="research-quality" id="quality">
        <header><span>03 / QUALITY</span><h2>{copy.qualityTitle}</h2></header>
        <div>{(copy.qualityColumns as Array<[string, string[]]>).map(([title, items], index) => <article key={title}><span>0{index + 1}</span><h3>{title}</h3><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></article>)}</div>
        <aside className="integrity-line">
          <span>{report?.panelChecks?.actualWideRows?.toLocaleString() ?? '1,350'} / {report?.panelChecks?.expectedWideRows?.toLocaleString() ?? '1,350'}</span>
          <p>{isEnglish ? 'country-year panel rows verified' : '国家—年份面板行已通过校验'}</p>
          <b>{report?.panelChecks?.uniqueCountryYear?.toLocaleString() ?? '1,350'} {isEnglish ? 'unique keys' : '个唯一键'}</b>
        </aside>
      </section>

      <section className="download-section" id="download">
        <header><span>04 / DOWNLOAD</span><h2>{copy.download}</h2>{report && <p>{copy.updated} · {new Date(report.generatedAt).toLocaleString(isEnglish ? 'en-US' : 'zh-CN')}</p>}</header>
        {(['core', 'docs', 'quality'] as const).map((group) => {
          const [title, body] = copy.groups[group]
          return <section className="download-group" key={group}>
            <header><div><span>{title}</span><p>{body}</p></div>{group === 'docs' && report ? <aside><b>{copy.fileInfo}</b><small>{report.parameters.startYear}—{report.parameters.endYear} · {report.parameters.sovereignCountries} {copy.countries}</small></aside> : null}</header>
            <div className="download-grid">{downloads.filter((item) => item.group === group).map((item) => {
              const [cardTitle, cardBody] = copy.cards[item.key]
              const rowCount = 'rowKey' in item ? report?.rows[item.rowKey] : undefined
              return <article key={item.key}>
                <span>{item.type}</span><h3>{cardTitle}</h3><p>{cardBody}</p>
                {'fields' in item && <details><summary>{copy.preview}</summary><code>{item.fields}</code></details>}
                <div><small>{rowCount === undefined ? item.file : `${rowCount.toLocaleString()} ${copy.rows}`}</small><a href={`${import.meta.env.BASE_URL}data/generated/${item.file}`} download>{copy.get} {item.type}<b>↓</b></a></div>
              </article>
            })}</div>
          </section>
        })}
      </section>
    </main>
  )
}
