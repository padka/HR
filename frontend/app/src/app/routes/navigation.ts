import type { ReactNode } from 'react'

export type NavItem = {
  to: string
  label: string
  icon: ReactNode
  tone: string
}

export type NavIcons = {
  dashboard: ReactNode
  slots: ReactNode
  candidates: ReactNode
  recruiters: ReactNode
  cities: ReactNode
  messenger: ReactNode
  profile: ReactNode
  bot: ReactNode
  copilot: ReactNode
}

export const MOBILE_PRIMARY_TABS = 4

export const PAGE_TITLES: Array<{ match: (pathname: string) => boolean; title: string }> = [
  { match: (pathname) => pathname === '/app/incoming', title: 'Входящие' },
  { match: (pathname) => pathname === '/app/dashboard', title: 'Дашборд' },
  { match: (pathname) => pathname === '/app/slots', title: 'Слоты' },
  { match: (pathname) => pathname === '/app/candidates', title: 'Кандидаты' },
  { match: (pathname) => pathname.startsWith('/app/candidates/'), title: 'Кандидат' },
  { match: (pathname) => pathname === '/app/messenger', title: 'Чаты' },
  { match: (pathname) => pathname.startsWith('/app/profile'), title: 'Профиль' },
  { match: (pathname) => pathname.startsWith('/app/recruiters'), title: 'Рекрутёры' },
  { match: (pathname) => pathname.startsWith('/app/cities'), title: 'Города' },
  { match: (pathname) => pathname.startsWith('/app/copilot'), title: 'Copilot' },
  { match: (pathname) => pathname.startsWith('/app/system'), title: 'Система' },
]

export const DETAIL_ROUTE_PREFIXES = [
  '/app/candidates/',
  '/app/slots/create',
  '/app/recruiters/',
  '/app/cities/',
  '/app/questions/',
  '/app/templates/',
  '/app/test-builder/',
]

export const AMBIENT_BACKGROUND_ROUTES = ['/app', '/app/dashboard', '/app/login']

export const normalizePathname = (pathname: string) => pathname.replace(/\/+$/, '') || '/'

export const isPathActive = (pathname: string, targetPath: string) => {
  const current = normalizePathname(pathname)
  const target = normalizePathname(targetPath)
  return current === target || current.startsWith(`${target}/`)
}

export const isDetailRoute = (pathname: string) => {
  if (pathname === '/app') return false
  if (pathname === '/app/login') return false
  return DETAIL_ROUTE_PREFIXES.some((prefix) => pathname.startsWith(prefix))
}

export const getMobileTitle = (pathname: string) => {
  const match = PAGE_TITLES.find((item) => item.match(pathname))
  return match?.title || 'Attila Recruiting'
}

export function buildNavItems({
  principalType,
  simulatorEnabled,
  icons,
}: {
  principalType?: string | null
  simulatorEnabled: boolean
  icons: NavIcons
}): NavItem[] {
  if (principalType === 'recruiter') {
    return [
      { to: '/app/incoming', label: 'Входящие', icon: icons.dashboard, tone: 'blue' },
      { to: '/app/candidates', label: 'Кандидаты', icon: icons.candidates, tone: 'sky' },
      { to: '/app/messenger', label: 'Чаты', icon: icons.messenger, tone: 'aqua' },
      { to: '/app/slots', label: 'Слоты', icon: icons.slots, tone: 'violet' },
      { to: '/app/detailization', label: 'Детализация', icon: icons.candidates, tone: 'mint' },
      { to: '/app/copilot', label: 'Copilot', icon: icons.copilot, tone: 'amber' },
      { to: '/app/profile', label: 'Профиль', icon: icons.profile, tone: 'slate' },
    ]
  }

  if (principalType === 'admin') {
    return [
      { to: '/app/dashboard', label: 'Дашборд', icon: icons.dashboard, tone: 'blue' },
      { to: '/app/slots', label: 'Слоты', icon: icons.slots, tone: 'violet' },
      { to: '/app/candidates', label: 'Кандидаты', icon: icons.candidates, tone: 'sky' },
      { to: '/app/messenger', label: 'Чаты', icon: icons.messenger, tone: 'aqua' },
      { to: '/app/detailization', label: 'Детализация', icon: icons.candidates, tone: 'mint' },
      { to: '/app/recruiters', label: 'Рекрутёры', icon: icons.recruiters, tone: 'indigo' },
      { to: '/app/cities', label: 'Города', icon: icons.cities, tone: 'sunset' },
      { to: '/app/copilot', label: 'Copilot', icon: icons.copilot, tone: 'amber' },
      ...(simulatorEnabled ? [{ to: '/app/simulator', label: 'Симулятор', icon: icons.slots, tone: 'violet' }] : []),
      { to: '/app/system', label: 'Система', icon: icons.bot, tone: 'emerald' },
      { to: '/app/profile', label: 'Профиль', icon: icons.profile, tone: 'slate' },
    ]
  }

  return []
}
