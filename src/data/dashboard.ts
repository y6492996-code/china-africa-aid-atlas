import { useEffect, useState } from 'react'

export interface CountryMetric {
  value: number
  known: number
  label: string
  unit: string
}

export interface CountryData {
  iso3: string
  nameEn: string
  nameZh: string
  records: number
  sourceCount: number
  sourceCounts: Record<string, number>
  yearMin: number | null
  yearMax: number | null
  yearCounts: Record<string, number>
  metrics: Record<string, CountryMetric>
}

export interface SourceData {
  id: string
  label: string
  rows: number
  mappedRows: number
  mappedRate: number
  metricKnownRate: number
  yearMin: number | null
  yearMax: number | null
  fieldCount?: number
  columns: Array<{ file: string; fields: string[] }>
}

export interface DashboardData {
  generatedAt: string
  global: {
    sourceCount: number
    countryCount: number
    recordCount: number
    yearMin: number
    yearMax: number
    trendComparisonYearMax: number
    latestYearCoverage: 'partial' | 'observed'
  }
  sources: SourceData[]
  countries: Record<string, CountryData>
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/dashboard.json`, { signal: controller.signal })
      .then((response) => response.json())
      .then(setData)
      .catch((reason) => {
        if (reason?.name !== 'AbortError') setFailed(true)
      })
    return () => controller.abort()
  }, [])

  return { data, failed }
}

export function recordsInRange(country: CountryData, start: number, end: number) {
  return Object.entries(country.yearCounts).reduce((sum, [year, value]) => {
    const numericYear = Number(year)
    return numericYear >= start && numericYear <= end ? sum + value : sum
  }, 0)
}
