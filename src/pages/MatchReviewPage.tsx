import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

type DecisionValue = 'same_project' | 'different_project' | 'uncertain'

interface ReviewRow {
  candidate_id: string
  country_iso3: string
  year: number
  similarity: number
  review_hint: string
  suggested_decision: string
  suggestion_confidence: string
  suggestion_reason: string
  left_source: string
  left_record_id: string
  left_title: string
  left_amount_value: number | string
  left_price_basis: string
  left_fund_type: string
  left_sector: string
  right_source: string
  right_record_id: string
  right_title: string
  right_amount_value: number | string
  right_price_basis: string
  right_fund_type: string
  right_sector: string
  amount_ratio_if_comparable: number | string
}

interface ReviewDecision {
  decision: DecisionValue
  notes: string
  reviewedAt: string
}

const STORAGE_KEY = 'caad-match-review-v1'

function loadDecisions(): Record<string, ReviewDecision> {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function csvCell(value: string) {
  return `"${value.replaceAll('"', '""')}"`
}

function displayAmount(value: number | string, locale: string) {
  if (value === '' || value === null || value === undefined) return '—'
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toLocaleString(locale, { maximumFractionDigits: 2 }) : String(value)
}

export function MatchReviewPage() {
  const { i18n } = useTranslation()
  const isEnglish = i18n.resolvedLanguage === 'en'
  const locale = isEnglish ? 'en-US' : 'zh-CN'
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [appliedReviewCount, setAppliedReviewCount] = useState(0)
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'failed'>('loading')
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>(loadDecisions)
  const [statusFilter, setStatusFilter] = useState('pending')
  const [hintFilter, setHintFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [activeId, setActiveId] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/generated/match_review_queue.json`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('queue unavailable')))
      .then((payload) => { setRows(payload.rows ?? []); setAppliedReviewCount(Number(payload.appliedReviewCount ?? 0)); setLoadState('ready') })
      .catch((reason) => { if (reason?.name !== 'AbortError') setLoadState('failed') })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions))
  }, [decisions])

  const visibleRows = useMemo(() => rows.filter((row) => {
    const decision = decisions[row.candidate_id]?.decision
    const statusMatch = statusFilter === 'all'
      || (statusFilter === 'pending' && !decision)
      || decision === statusFilter
    const hintMatch = hintFilter === 'all' || row.review_hint === hintFilter
    const normalizedQuery = query.trim().toLocaleLowerCase()
    const queryMatch = !normalizedQuery || [
      row.candidate_id, row.country_iso3, row.left_source, row.left_record_id,
      row.left_title, row.right_source, row.right_record_id, row.right_title,
    ].some((value) => String(value).toLocaleLowerCase().includes(normalizedQuery))
    return statusMatch && hintMatch && queryMatch
  }), [decisions, hintFilter, query, rows, statusFilter])

  const active = visibleRows.find((row) => row.candidate_id === activeId) ?? visibleRows[0]
  const reviewedCount = Object.keys(decisions).filter((id) => rows.some((row) => row.candidate_id === id)).length
  const reviewComplete = loadState === 'ready' && rows.length === 0
  const displayReviewedCount = appliedReviewCount + reviewedCount
  const displayTotal = appliedReviewCount + rows.length
  const currentDecision = active ? decisions[active.candidate_id] : undefined
  const comparisonRecords = active ? [
    { key: 'left', title: active.left_title, source: active.left_source, recordId: active.left_record_id, amount: active.left_amount_value, priceBasis: active.left_price_basis, fundType: active.left_fund_type, sector: active.left_sector },
    { key: 'right', title: active.right_title, source: active.right_source, recordId: active.right_record_id, amount: active.right_amount_value, priceBasis: active.right_price_basis, fundType: active.right_fund_type, sector: active.right_sector },
  ] : []

  function decide(decision: DecisionValue) {
    if (!active) return
    setDecisions((current) => ({
      ...current,
      [active.candidate_id]: {
        decision,
        notes: current[active.candidate_id]?.notes ?? '',
        reviewedAt: new Date().toISOString(),
      },
    }))
    const nextIndex = visibleRows.findIndex((row) => row.candidate_id === active.candidate_id) + 1
    setActiveId(visibleRows[nextIndex]?.candidate_id ?? active.candidate_id)
  }

  function updateNotes(notes: string) {
    if (!active) return
    setDecisions((current) => ({
      ...current,
      [active.candidate_id]: {
        decision: current[active.candidate_id]?.decision ?? 'uncertain',
        notes,
        reviewedAt: new Date().toISOString(),
      },
    }))
  }

  function exportDecisions() {
    const header = ['candidate_id', 'left_source', 'left_record_id', 'right_source', 'right_record_id', 'review_decision', 'review_notes', 'reviewed_at']
    const body = rows.flatMap((row) => {
      const decision = decisions[row.candidate_id]
      if (!decision) return []
      return [[
        row.candidate_id, row.left_source, row.left_record_id, row.right_source,
        row.right_record_id, decision.decision, decision.notes, decision.reviewedAt,
      ].map((value) => csvCell(String(value))).join(',')]
    })
    const blob = new Blob([`\uFEFF${[header.join(','), ...body].join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'match_review_decisions.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  function importDecisions(file: File) {
    file.text().then((text) => {
      const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean)
      if (lines.length < 2) return
      const parseLine = (line: string) => {
        const values: string[] = []
        let value = ''
        let quoted = false
        for (let index = 0; index < line.length; index += 1) {
          const character = line[index]
          if (character === '"' && quoted && line[index + 1] === '"') { value += '"'; index += 1 }
          else if (character === '"') quoted = !quoted
          else if (character === ',' && !quoted) { values.push(value); value = '' }
          else value += character
        }
        values.push(value)
        return values
      }
      const headers = parseLine(lines[0])
      const imported: Record<string, ReviewDecision> = {}
      lines.slice(1).forEach((line) => {
        const values = parseLine(line)
        const row = Object.fromEntries(headers.map((header, index) => [header, values[index] ?? '']))
        if (row.candidate_id && ['same_project', 'different_project', 'uncertain'].includes(row.review_decision)) {
          imported[row.candidate_id] = { decision: row.review_decision as DecisionValue, notes: row.review_notes, reviewedAt: row.reviewed_at || new Date().toISOString() }
        }
      })
      setDecisions((current) => ({ ...current, ...imported }))
    })
  }

  const copy = isEnglish ? {
    kicker: 'MATCH / REVIEW', title: 'Project match review',
    body: 'Review candidate duplicate records across databases and classify each pair as the same project, different projects or uncertain.',
    reviewed: 'reviewed', remaining: 'remaining', total: 'candidate pairs', export: 'Export decisions', import: 'Import decisions',
    search: 'Search title, source, record ID or country', all: 'All', pending: 'Pending',
    same: 'Same project', different: 'Different projects', uncertain: 'Uncertain',
    markAs: 'Mark current pair as',
    allHints: 'All review types', qualifier: 'Qualifier conflict', sector: 'Sector conflict', titleHint: 'Title similarity',
    queue: 'Review queue', empty: 'No candidates match these filters.', similarity: 'title similarity',
    suggestion: 'Algorithmic cue', highCue: 'High-confidence suggestion: different projects',
    manualCue: 'Manual comparison required', sourceRecord: 'source record', amount: 'amount',
    basis: 'price basis', fund: 'fund type', sectorLabel: 'sector', ratio: 'comparable amount ratio',
    notes: 'Review notes', notesPlaceholder: 'Record the decisive evidence or unresolved question…', completeTitle: 'Current review is complete', completeBody: 'All candidate pairs have been reviewed. There are no pending records.', failed: 'Data could not be loaded. Confirm that the local site is running, then refresh this page.',
  } : {
    kicker: '匹配 / 审核', title: '项目匹配审核',
    body: '逐对审核跨数据库疑似重复记录，并选择同一项目、不同项目或暂不确定。',
    reviewed: '对已审核', remaining: '对待审核', total: '对候选', export: '导出审核决定', import: '导入审核决定',
    search: '搜索标题、来源、记录ID或国家', all: '全部', pending: '待审核',
    same: '同一项目', different: '不同项目', uncertain: '暂不确定',
    markAs: '将当前候选标记为',
    allHints: '全部审核类型', qualifier: '限定词冲突', sector: '行业冲突', titleHint: '标题相似',
    queue: '审核队列', empty: '当前筛选下没有候选。', similarity: '标题相似度',
    suggestion: '算法提示', highCue: '高置信建议：不同项目', manualCue: '需要人工比较',
    sourceRecord: '来源记录', amount: '金额', basis: '价格基期', fund: '资金性质',
    sectorLabel: '行业', ratio: '可比金额比值', notes: '审核备注',
    notesPlaceholder: '记录作出判断的关键证据，或仍未解决的问题……', completeTitle: '当前审核已完成', completeBody: '全部候选均已审核，暂无待审核记录。', failed: '数据加载失败，请确认本地网站已启动后刷新页面。',
  }

  return <main id="main-content" className="review-page">
    <header className="review-hero"><span>{copy.kicker}</span><h1>{copy.title}</h1><p>{copy.body}</p><div className="review-progress"><div><strong>{displayReviewedCount}</strong><span>{copy.reviewed}</span></div><div><strong>{loadState === 'loading' ? '—' : Math.max(rows.length - reviewedCount, 0)}</strong><span>{copy.remaining}</span></div><div><strong>{displayTotal}</strong><span>{copy.total}</span></div><div className="review-file-actions"><label>{copy.import}<input type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (file) importDecisions(file) }} /></label><button type="button" onClick={exportDecisions} disabled={!reviewedCount}>{copy.export}<b>↓</b></button></div></div></header>
    <section className="review-toolbar" aria-label={copy.queue}><label><span>{copy.search}</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={copy.search} /></label><div className="review-filter">{[
      ['pending', copy.pending], ['all', copy.all], ['same_project', copy.same], ['different_project', copy.different], ['uncertain', copy.uncertain],
    ].map(([value, label]) => <button key={value} type="button" className={statusFilter === value ? 'active' : ''} onClick={() => setStatusFilter(value)}>{label}</button>)}</div><select value={hintFilter} onChange={(event) => setHintFilter(event.target.value)} aria-label={copy.allHints}><option value="all">{copy.allHints}</option><option value="qualifier_conflict_check_separate_projects">{copy.qualifier}</option><option value="sector_conflict_check_context">{copy.sector}</option><option value="title_similarity_check_same_project">{copy.titleHint}</option></select></section>
    <section className="review-workbench">
      <aside className="review-queue"><header><span>{copy.queue}</span><strong>{visibleRows.length}</strong></header><div>{visibleRows.map((row) => <button type="button" key={row.candidate_id} className={active?.candidate_id === row.candidate_id ? 'active' : ''} onClick={() => setActiveId(row.candidate_id)}><i className={decisions[row.candidate_id] ? `is-${decisions[row.candidate_id].decision}` : ''} /><span><b>{row.country_iso3} · {row.year}</b><small>{row.left_source} × {row.right_source}</small></span><em>{Math.round(Number(row.similarity) * 100)}%</em></button>)}</div></aside>
      <div className="review-detail">{active ? <>
        <header><div><span>{active.country_iso3} · {active.year}</span><small>{active.candidate_id}</small></div><strong>{Math.round(Number(active.similarity) * 100)}%<small>{copy.similarity}</small></strong></header>
        <aside className={active.suggested_decision ? 'review-cue is-high' : 'review-cue'}><span>{copy.suggestion}</span><strong>{active.suggested_decision ? copy.highCue : copy.manualCue}</strong><p>{active.suggestion_reason}</p></aside>
        <div className="record-comparison">{comparisonRecords.map((record) => <article key={record.key}><span>{copy.sourceRecord}</span><h2>{record.title}</h2><div className="record-id"><b>{record.source}</b><small>{record.recordId}</small></div><dl><div><dt>{copy.amount}</dt><dd>{displayAmount(record.amount, locale)}</dd></div><div><dt>{copy.basis}</dt><dd>{record.priceBasis || '—'}</dd></div><div><dt>{copy.fund}</dt><dd>{record.fundType || '—'}</dd></div><div><dt>{copy.sectorLabel}</dt><dd>{record.sector || '—'}</dd></div></dl></article>)}</div>
        {active.amount_ratio_if_comparable !== '' && <p className="amount-ratio">{copy.ratio} <strong>{Number(active.amount_ratio_if_comparable).toFixed(3)}</strong></p>}
        <div className="decision-panel"><div><button type="button" aria-label={`${copy.markAs}：${copy.same}`} className={currentDecision?.decision === 'same_project' ? 'active is-same' : ''} onClick={() => decide('same_project')}>{copy.same}</button><button type="button" aria-label={`${copy.markAs}：${copy.different}`} className={currentDecision?.decision === 'different_project' ? 'active is-different' : ''} onClick={() => decide('different_project')}>{copy.different}</button><button type="button" aria-label={`${copy.markAs}：${copy.uncertain}`} className={currentDecision?.decision === 'uncertain' ? 'active is-uncertain' : ''} onClick={() => decide('uncertain')}>{copy.uncertain}</button></div><label><span>{copy.notes}</span><textarea value={currentDecision?.notes ?? ''} onChange={(event) => updateNotes(event.target.value)} placeholder={copy.notesPlaceholder} /></label></div>
      </> : <div className="review-empty"><strong>{loadState === 'failed' ? copy.failed : reviewComplete || (statusFilter === 'pending' && reviewedCount === rows.length && rows.length) ? copy.completeTitle : copy.empty}</strong>{loadState !== 'failed' && (reviewComplete || (statusFilter === 'pending' && reviewedCount === rows.length && rows.length)) ? <span>{copy.completeBody}</span> : null}</div>}</div>
    </section>
  </main>
}
