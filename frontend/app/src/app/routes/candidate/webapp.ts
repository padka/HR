import { readCandidatePortalAccessToken, writeCandidatePortalAccessToken } from '@/shared/candidate-portal-session'

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

export type CandidatePortalTokenSource = 'route' | 'location' | 'bridge' | 'storage' | 'none'

export type CandidatePortalTokenResolution = {
  token: string
  source: CandidatePortalTokenSource
  direct: boolean
}

const MAX_BRIDGE_SCRIPT_ID = 'max-web-app-bridge'
const MAX_BRIDGE_SCRIPT_SRC = 'https://st.max.ru/js/max-web-app.js'

let bridgeLoadPromise: Promise<CandidateWebAppBridge | null> | null = null

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

function decodePortalToken(value: string): string {
  if (!value) return ''
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function resolvePortalTokenFromLocation(routeToken?: string): CandidatePortalTokenResolution {
  const tokenFromRoute = (routeToken || '').trim()
  if (tokenFromRoute) {
    return {
      token: tokenFromRoute,
      source: 'route',
      direct: true,
    }
  }
  if (typeof window === 'undefined') {
    return {
      token: '',
      source: 'none',
      direct: false,
    }
  }

  const fromPath = window.location.pathname.match(/\/candidate\/start\/([^/?#]+)/)
  if (fromPath?.[1]) {
    return {
      token: decodePortalToken(fromPath[1]),
      source: 'location',
      direct: true,
    }
  }

  const search = new URLSearchParams(window.location.search)
  const fromQuery = search.get('token') || search.get('start') || search.get('startapp') || ''
  if (fromQuery) {
    return {
      token: decodePortalToken(fromQuery),
      source: 'location',
      direct: true,
    }
  }
  return {
    token: '',
    source: 'none',
    direct: false,
  }
}

export function hasCandidatePortalLocationToken(routeToken?: string) {
  return Boolean(resolvePortalTokenFromLocation(routeToken).token)
}

export async function ensureCandidateWebAppBridge(timeoutMs = 250): Promise<CandidateWebAppBridge | null> {
  const existingBridge = getWebAppBridge()
  if (existingBridge) return existingBridge
  if (typeof window === 'undefined' || typeof document === 'undefined') return null
  if (bridgeLoadPromise) return bridgeLoadPromise

  bridgeLoadPromise = new Promise((resolve) => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      bridgeLoadPromise = null
      resolve(getWebAppBridge())
    }

    const timer = window.setTimeout(() => {
      finish()
    }, timeoutMs)

    const cleanupAndFinish = () => {
      window.clearTimeout(timer)
      finish()
    }

    let script = document.getElementById(MAX_BRIDGE_SCRIPT_ID) as HTMLScriptElement | null
    if (!script) {
      script = document.createElement('script')
      script.id = MAX_BRIDGE_SCRIPT_ID
      script.src = MAX_BRIDGE_SCRIPT_SRC
      script.async = true
      script.defer = true
      document.head.appendChild(script)
    } else if (script.dataset.loaded === 'true') {
      cleanupAndFinish()
      return
    }

    script.addEventListener(
      'load',
      () => {
        script!.dataset.loaded = 'true'
        cleanupAndFinish()
      },
      { once: true },
    )
    script.addEventListener(
      'error',
      () => {
        cleanupAndFinish()
      },
      { once: true },
    )
  })

  return bridgeLoadPromise
}

export function markCandidateWebAppReady() {
  const bridge = getWebAppBridge()
  bridge?.ready?.()
}

export function readCandidateWebAppInitData(): string {
  const bridge = getWebAppBridge()
  return typeof bridge?.initData === 'string' ? bridge.initData.trim() : ''
}

export function resolveCandidatePortalToken(routeToken?: string): CandidatePortalTokenResolution {
  const locationToken = resolvePortalTokenFromLocation(routeToken)
  if (locationToken.token) return locationToken

  const bridge = getWebAppBridge()
  const startParam = extractStartParam(bridge?.initDataUnsafe?.start_param)
  if (startParam) {
    return {
      token: decodePortalToken(startParam),
      source: 'bridge',
      direct: true,
    }
  }

  const storedToken = readCandidatePortalAccessToken()
  if (storedToken) {
    return {
      token: storedToken,
      source: 'storage',
      direct: false,
    }
  }

  return {
    token: '',
    source: 'none',
    direct: false,
  }
}

export function persistCandidatePortalAccessToken(token: string) {
  writeCandidatePortalAccessToken(token)
}
