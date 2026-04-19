export type MaxContactPayload = Record<string, unknown> | null

const MAX_BRIDGE_SCRIPT_SRC = 'https://st.max.ru/js/max-web-app.js'

let bridgeBootstrapPromise: Promise<void> | null = null

type MaxBackButton = {
  show?: () => void
  hide?: () => void
  onClick?: (callback: () => void) => void
  offClick?: (callback: () => void) => void
}

type MaxBridge = {
  initData?: string
  initDataUnsafe?: {
    start_param?: string
  }
  ready?: () => void
  expand?: () => void
  requestContact?: () => unknown
  enableClosingConfirmation?: () => void
  disableClosingConfirmation?: () => void
  openMaxLink?: (url: string) => void
  openLink?: (url: string) => void
  BackButton?: MaxBackButton
}

declare global {
  interface Window {
    WebApp?: MaxBridge
  }
}

function getBridge(): MaxBridge | null {
  if (typeof window === 'undefined') return null
  return window.WebApp || null
}

function loadMaxBridgeScript(): Promise<void> {
  if (getBridge()) {
    return Promise.resolve()
  }
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return Promise.resolve()
  }
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${MAX_BRIDGE_SCRIPT_SRC}"]`)
  if (existing) {
    if (existing.dataset.loaded === 'true') return Promise.resolve()
    return new Promise((resolve) => {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => resolve(), { once: true })
    })
  }

  return new Promise((resolve) => {
    const script = document.createElement('script')
    script.src = MAX_BRIDGE_SCRIPT_SRC
    script.async = true
    script.dataset.maxBridge = 'true'
    script.addEventListener(
      'load',
      () => {
        script.dataset.loaded = 'true'
        resolve()
      },
      { once: true },
    )
    script.addEventListener('error', () => resolve(), { once: true })
    document.head.appendChild(script)
  })
}

export function bridgeInitData(): string {
  return String(getBridge()?.initData || '').trim()
}

export function bridgeStartParam(): string {
  return String(getBridge()?.initDataUnsafe?.start_param || '').trim()
}

export function prepareMaxBridge(): Promise<void> {
  if (!bridgeBootstrapPromise) {
    bridgeBootstrapPromise = loadMaxBridgeScript().then(() => undefined)
  }
  return bridgeBootstrapPromise.then(() => {
    const bridge = getBridge()
    bridge?.ready?.()
    bridge?.expand?.()
  })
}

export async function requestMaxContact(): Promise<{ phone: string | null; contact: MaxContactPayload }> {
  const bridge = getBridge()
  if (!bridge?.requestContact) return { phone: null, contact: null }
  const result = await Promise.resolve(bridge.requestContact())
  if (typeof result === 'string') {
    const phone = result.trim()
    return { phone: phone || null, contact: phone ? { phone } : null }
  }
  if (result && typeof result === 'object') {
    const contact = result as Record<string, unknown>
    for (const key of ['phone_number', 'phone', 'msisdn']) {
      const value = contact[key]
      if (typeof value === 'string' && value.trim()) {
        return { phone: value.trim(), contact }
      }
    }
    return { phone: null, contact }
  }
  return { phone: null, contact: null }
}

export function bindMaxBackButton(callback: () => void): () => void {
  const bridge = getBridge()
  const backButton = bridge?.BackButton
  backButton?.show?.()
  backButton?.onClick?.(callback)
  return () => {
    backButton?.offClick?.(callback)
    backButton?.hide?.()
  }
}

export function setClosingConfirmation(enabled: boolean) {
  const bridge = getBridge()
  if (enabled) {
    bridge?.enableClosingConfirmation?.()
    return
  }
  bridge?.disableClosingConfirmation?.()
}

export function openMaxDeepLink(url: string): boolean {
  const bridge = getBridge()
  if (!bridge?.openMaxLink || !/^https:\/\/max\.ru\//i.test(url)) return false
  bridge.openMaxLink(url)
  return true
}

export function openExternalLink(url: string): boolean {
  const bridge = getBridge()
  if (!bridge?.openLink) return false
  bridge.openLink(url)
  return true
}
