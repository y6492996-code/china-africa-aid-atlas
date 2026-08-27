export const routes = [
  { path: '/', key: 'home' },
  { path: '/databases', key: 'databases' },
  { path: '/trends', key: 'trends' },
  { path: '/countries', key: 'countries' },
  { path: '/sectors', key: 'sectors' },
  { path: '/records', key: 'records' },
  { path: '/topics', key: 'topics' },
  { path: '/quality', key: 'quality' },
  { path: '/findings', key: 'findings' },
  { path: '/review', key: 'review' },
  { path: '/methods', key: 'methods' }
] as const

export type PageKey = Exclude<(typeof routes)[number]['key'], 'home'>
