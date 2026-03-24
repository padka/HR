type CandidateWebAppUnsafeData = {
  start_param?: unknown
}

type CandidateWebAppBridge = {
  initData?: string
  initDataUnsafe?: CandidateWebAppUnsafeData
  ready?: () => void
}

type CandidateWebAppWindow = Window & {
  WebApp?: CandidateWebAppBridge
  Telegram?: {
    WebApp?: CandidateWebAppBridge
  }
}

function getWebAppBridge(): CandidateWebAppBridge | null {
  if (typeof window === 'undefined') return null
  const candidateWindow = window as CandidateWebAppWindow
  return candidateWindow.WebApp || candidateWindow.Telegram?.WebApp || null
}

function extractStartParam(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim()
  }
  if (!value || typeof value !== 'object') {
    return ''
  }
  const record = value as Record<string, unknown>
  const candidates = [record.start_param, record.payload, record.value, record.token]
  for (const item of candidates) {
    const next = extractStartParam(item)
    if (next) return next
  }
  return ''
}

export function markCandidateWebAppReady() {
  const bridge = getWebAppBridge()
  bridge?.ready?.()
}

export function resolveCandidatePortalToken(routeToken?: string) {
  const tokenFromRoute = (routeToken || '').trim()
  if (tokenFromRoute) return tokenFromRoute
  const storedToken = readCandidatePortalAccessToken()
  if (storedToken) return storedToken
  if (typeof window === 'undefined') return ''

  const fromPath = window.location.pathname.match(/\/candidate\/start\/([^/?#]+)/)
  if (fromPath?.[1]) {
    try {
      return decodeURIComponent(fromPath[1])
    } catch {
      return fromPath[1]
    }
  }

  const search = new URLSearchParams(window.location.search)
  const fromQuery = search.get('token') || search.get('start') || search.get('startapp') || ''
  if (fromQuery) {
    try {
      return decodeURIComponent(fromQuery)
    } catch {
      return fromQuery
    }
  }

  const bridge = getWebAppBridge()
  const startParam = extractStartParam(bridge?.initDataUnsafe?.start_param)
  if (!startParam) return ''
  try {
    const decoded = decodeURIComponent(startParam)
    if (decoded) writeCandidatePortalAccessToken(decoded)
    return decoded
  } catch {
    if (startParam) writeCandidatePortalAccessToken(startParam)
    return startParam
  }
}

export function persistCandidatePortalAccessToken(token: string) {
  writeCandidatePortalAccessToken(token)
}
import { readCandidatePortalAccessToken, writeCandidatePortalAccessToken } from '@/shared/candidate-portal-session'
