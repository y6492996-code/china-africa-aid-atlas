export type SourceStatus = 'missing' | 'available' | 'invalid' | 'built'

export type SourceCategory = 'aid' | 'finance' | 'debt' | 'investment' | 'energy' | 'health'

export interface SourceDefinition {
  id: string
  name: string
  shortName: string
  category: SourceCategory
  level: string
  records: number
  countries: number
  startYear: number
  endYear: number
  files: string[]
  amountBasis: string
  status: SourceStatus
  description: string
}

export const sourceRegistry: SourceDefinition[] = [
  {
    id: 'aiddata', name: 'AidData Global Chinese Development Finance', shortName: 'AidData', category: 'aid',
    level: '项目', records: 8957, countries: 53, startYear: 2000, endYear: 2023,
    files: ['aiddata_africa_clean.csv'], amountBasis: '项目承诺金额（美元）', status: 'available',
    description: '覆盖援助与发展融资项目，适合项目级检索、部门结构和资金流类型分析。',
  },
  {
    id: 'codf', name: 'China Overseas Development Finance Database', shortName: 'CODF', category: 'finance',
    level: '贷款', records: 576, countries: 45, startYear: 2008, endYear: 2024,
    files: ['bu_codf_africa_clean.csv'], amountBasis: '贷款金额（美元）', status: 'available',
    description: '聚焦中国开发性金融机构的海外贷款，保留项目、行业和能源类型字段。',
  },
  {
    id: 'cla', name: 'Chinese Loans to Africa Database', shortName: 'CLA', category: 'finance',
    level: '贷款', records: 1319, countries: 50, startYear: 2000, endYear: 2024,
    files: ['cla_africa_clean.csv'], amountBasis: '贷款金额（百万美元）', status: 'available',
    description: '面向非洲的中国贷款项目数据库，可用于贷款方、行业和国别比较。',
  },
  {
    id: 'debt', name: 'Debt Cancellation & Restructuring', shortName: 'Debt', category: 'debt',
    level: '债务事件', records: 112, countries: 42, startYear: 2001, endYear: 2019,
    files: ['cancellation_africa_clean.csv', 'restructuring_africa_clean.csv'], amountBasis: '取消或重组金额（百万美元）', status: 'available',
    description: '合并债务取消与重组事件，但保留事件类型、估算标记和原始来源。',
  },
  {
    id: 'exports', name: 'Chinese Aid Exports Database', shortName: 'Aid Exports', category: 'aid',
    level: '国家—月份', records: 6156, countries: 54, startYear: 2015, endYear: 2024,
    files: ['africa_aid_data_clean.csv'], amountBasis: '援助出口价值', status: 'available',
    description: '按国家和月份记录援助出口，并区分医疗与非医疗援助。',
  },
  {
    id: 'fdi', name: 'Chinese FDI in Africa', shortName: 'FDI', category: 'investment',
    level: '国家—年份', records: 1232, countries: 56, startYear: 2003, endYear: 2024,
    files: ['fdi_africa_panel.csv', 'fdi_africa_sector_aggregate.csv', 'fdi_africa_metadata.csv'], amountBasis: '流量与存量（美元）', status: 'available',
    description: '包含对非直接投资流量、存量以及行业汇总，适合宏观趋势分析。',
  },
  {
    id: 'cofi', name: 'China Overseas Finance Inventory', shortName: 'COFI', category: 'energy',
    level: '电力融资事件', records: 114, countries: 35, startYear: 1967, endYear: 2030,
    files: ['cofi_africa_clean.csv'], amountBasis: '债权与股权投资（美元）', status: 'available',
    description: '电力项目融资清单，包含装机容量、燃料、投资类型和金融机构字段；末期含规划项目。',
  },
  {
    id: 'cgef', name: "China's Global Energy Finance Database", shortName: 'CGEF', category: 'energy',
    level: '能源贷款', records: 146, countries: 34, startYear: 2002, endYear: 2023,
    files: ['CGEF_Africa_2024_Cleaned.csv'], amountBasis: '贷款金额（百万美元）', status: 'available',
    description: '能源领域贷款项目，支持能源类型、贷款方与借款方分析。',
  },
  {
    id: 'cgp', name: "China's Global Power Database", shortName: 'CGP', category: 'energy',
    level: '发电机组', records: 165, countries: 29, startYear: 2002, endYear: 2027,
    files: ['CGP_Africa_2025_Cleaned.csv'], amountBasis: '装机容量与融资信息', status: 'available',
    description: '从电厂细化到发电机组，包含技术、状态、容量和投融资关系；末期含计划投产机组。',
  },
  {
    id: 'chapo', name: "Mapping China's Health Assistance Projects Overseas", shortName: 'CHAPO', category: 'health',
    level: '卫生项目', records: 1972, countries: 52, startYear: 2000, endYear: 2021,
    files: ['chapo_africa_clean.csv'], amountBasis: '2021年不变价美元（部分缺失）', status: 'available',
    description: '卫生援助项目数据库，覆盖医疗队、培训、物资、设施和重点疾病。',
  },
  {
    id: 'ihme', name: 'IHME Development Assistance for Health', shortName: 'IHME DAH', category: 'health',
    level: '来源—渠道—国家—年份', records: 300444, countries: 54, startYear: 1990, endYear: 2023,
    files: ['ihme_dah_africa_clean.csv'], amountBasis: '2023年不变价百万美元', status: 'available',
    description: '卫生发展援助的长时间序列，细分来源、渠道、受援国和疾病主题。',
  },
  {
    id: 'china_eu_finance', name: 'Development Finance of China and the EU to Africa', shortName: 'China–EU Finance', category: 'finance',
    level: '国家—年份', records: 884, countries: 52, startYear: 2000, endYear: 2017,
    files: ['china_africa_finance_cleaned.csv'], amountBasis: '发展融资及宏观指标', status: 'available',
    description: '中国与欧盟对非发展融资面板，附带贸易、治理与宏观控制变量。',
  },
]
