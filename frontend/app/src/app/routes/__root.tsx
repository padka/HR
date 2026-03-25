import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { apiFetch, queryClient } from '@/api/client'

import { createBubblePopFx, type BubblePopFx } from './bubble-pop-fx'
import {
  AMBIENT_BACKGROUND_ROUTES,
  MOBILE_PRIMARY_TABS,
  buildNavItems,
  getMobileTitle,
  isDetailRoute,
  isPathActive,
  normalizePathname,
} from './navigation'

const LIQUID_GLASS_V2_OVERRIDE_KEY = 'ui:liquidGlassV2'
const LIQUID_GLASS_V2_DATASET_VALUE = 'liquid-glass-v2'

type MotionMode = 'full' | 'reduced'

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const clamp01 = (value: number) => clamp(value, 0, 1)

const envLiquidGlassV2Enabled = String(import.meta.env.VITE_LIQUID_GLASS_V2 || '1') === '1'

function resolveLiquidGlassV2Enabled() {
  if (typeof window === 'undefined') return envLiquidGlassV2Enabled
  const override = window.localStorage.getItem(LIQUID_GLASS_V2_OVERRIDE_KEY)?.trim().toLowerCase()
  if (override === '1' || override === 'true' || override === 'on') return true
  if (override === '0' || override === 'false' || override === 'off') return false
  return envLiquidGlassV2Enabled
}

function resolveMotionMode(): MotionMode {
  if (typeof window === 'undefined') return 'full'
  return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ? 'reduced' : 'full'
}

type ThreadItem = {
  id: number
  candidate_id: number
  type: 'candidate'
  title: string
  city?: string | null
  status_label?: string | null
  profile_url?: string | null
  created_at: string
  last_message_at?: string | null
  last_message?: {
    text?: string | null
    created_at?: string | null
    direction?: string | null
  }
  unread_count?: number
}

type ThreadsPayload = {
  threads: ThreadItem[]
  latest_event_at?: string | null
  updated?: boolean
}

const ICONS = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  slots: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  ),
  candidates: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="8.5" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  recruiters: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  cities: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),
  messenger: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
      <path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662" />
    </svg>
  ),
  bot: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v2" />
      <path d="M8 5h8" />
      <rect x="4" y="7" width="16" height="14" rx="3" />
      <path d="M9 12h.01M15 12h.01" />
      <path d="M8 16h8" />
    </svg>
  ),
  copilot: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2l1.4 6.2L20 10l-6.6 1.8L12 18l-1.4-6.2L4 10l6.6-1.8L12 2z" />
      <path d="M5 20l1-3" />
      <path d="M19 20l-1-3" />
    </svg>
  ),
  more: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="6" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="18" cy="12" r="1.6" />
    </svg>
  ),
}

export function RootLayout() {
  const { location } = useRouterState()
  const isMobile = useIsMobile()
  const [liquidGlassV2Enabled, setLiquidGlassV2Enabled] = useState<boolean>(resolveLiquidGlassV2Enabled)
  const [motionMode, setMotionMode] = useState<MotionMode>(resolveMotionMode)
  const hideNav = location.pathname.startsWith('/app/login')
    || location.pathname.startsWith('/tg-app')
    || location.pathname.startsWith('/candidate')
  const profileQuery = useProfile(!hideNav)
  const principalType = profileQuery.data?.principal.type
  const authError = profileQuery.error as (Error & { status?: number }) | undefined
  const isUnauthed = authError?.status === 401
  const principalId = profileQuery.data?.principal.id

  const [chatToast, setChatToast] = useState<{ title: string; preview: string; unreadCount: number } | null>(null)
  const [chatUnreadCount, setChatUnreadCount] = useState(0)
  const [isMoreSheetOpen, setIsMoreSheetOpen] = useState(false)
  const [mobileTransition, setMobileTransition] = useState<'push' | 'pop' | 'fade'>('fade')
  const chatToastTimerRef = useRef<number | null>(null)
  const moreButtonRef = useRef<HTMLButtonElement | null>(null)
  const wasMoreSheetOpenRef = useRef(false)
  const chatLastSeenRef = useRef<Record<number, string>>({})
  const chatInitializedRef = useRef(false)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const lastPathRef = useRef(location.pathname)

  const bubbleStateRef = useRef<{
    hovered: HTMLSpanElement | null
    moveRaf: number | null
    lastX: number
    lastY: number
    timers: number[]
    layers: {
      layer1: HTMLSpanElement[]
      layer2: HTMLSpanElement[]
      layer3: HTMLSpanElement[]
    }
  }>({
    hovered: null,
    moveRaf: null,
    lastX: 0,
    lastY: 0,
    timers: [],
    layers: { layer1: [], layer2: [], layer3: [] },
  })

  useEffect(() => {
    const syncUiMode = () => setLiquidGlassV2Enabled(resolveLiquidGlassV2Enabled())
    const onStorage = (event: StorageEvent) => {
      if (event.key === LIQUID_GLASS_V2_OVERRIDE_KEY) syncUiMode()
    }

    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', syncUiMode)
    document.addEventListener('visibilitychange', syncUiMode)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', syncUiMode)
      document.removeEventListener('visibilitychange', syncUiMode)
    }
  }, [])

  useEffect(() => {
    const storedTheme = window.localStorage.getItem('theme')
    if (storedTheme === 'dark' || storedTheme === 'light') {
      document.documentElement.dataset.theme = storedTheme
    }
  }, [])

  useEffect(() => {
    const root = document.documentElement
    if (liquidGlassV2Enabled) root.dataset.ui = LIQUID_GLASS_V2_DATASET_VALUE
    else delete root.dataset.ui
  }, [liquidGlassV2Enabled])

  useEffect(() => {
    const media: MediaQueryList | null =
      typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : null
    const syncMotionMode = () => setMotionMode(media?.matches ? 'reduced' : 'full')
    syncMotionMode()

    if (!media) return
    const listener = () => syncMotionMode()
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', listener)
      return () => media.removeEventListener('change', listener)
    }
    const legacyMedia = media as MediaQueryList & {
      addListener?: (listener: (this: MediaQueryList, ev: MediaQueryListEvent) => unknown) => void
      removeListener?: (listener: (this: MediaQueryList, ev: MediaQueryListEvent) => unknown) => void
    }
    if (typeof legacyMedia.addListener === 'function') {
      legacyMedia.addListener(listener)
      return () => legacyMedia.removeListener?.(listener)
    }
  }, [])

  useEffect(() => {
    document.documentElement.dataset.motion = motionMode
  }, [motionMode])

  useEffect(() => {
    const pageTitle = hideNav ? 'Attila Recruiting' : `${getMobileTitle(location.pathname)} • Attila Recruiting`
    document.title =
      !hideNav && chatUnreadCount > 0
        ? `(${chatUnreadCount > 99 ? '99+' : chatUnreadCount}) ${pageTitle}`
        : pageTitle
  }, [chatUnreadCount, hideNav, location.pathname])

  useEffect(() => {
    if (!isMobile) {
      setIsMoreSheetOpen(false)
      return
    }

    const prevPath = lastPathRef.current
    const nextPath = location.pathname
    if (prevPath === nextPath) return

    const prevDepth = prevPath.split('/').filter(Boolean).length
    const nextDepth = nextPath.split('/').filter(Boolean).length
    const transition: 'push' | 'pop' | 'fade' =
      nextDepth > prevDepth ? 'push' : nextDepth < prevDepth ? 'pop' : 'fade'

    setMobileTransition(transition)
    setIsMoreSheetOpen(false)
    lastPathRef.current = nextPath

    const timer = window.setTimeout(() => setMobileTransition('fade'), 340)
    return () => window.clearTimeout(timer)
  }, [isMobile, location.pathname])

  useEffect(() => {
    if (!isMobile) return
    if (!isMoreSheetOpen) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMoreSheetOpen(false)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isMobile, isMoreSheetOpen])

  useEffect(() => {
    if (!isMobile) return

    const nodes = [
      document.querySelector<HTMLElement>('.mobile-header'),
      document.querySelector<HTMLElement>('.app-main'),
      document.querySelector<HTMLElement>('.mobile-tab-bar'),
    ].filter((node): node is HTMLElement => node instanceof HTMLElement)

    if (isMoreSheetOpen) {
      wasMoreSheetOpenRef.current = true
      const prevBodyOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      nodes.forEach((node) => {
        node.setAttribute('aria-hidden', 'true')
        node.setAttribute('inert', '')
      })

      return () => {
        document.body.style.overflow = prevBodyOverflow
        nodes.forEach((node) => {
          node.removeAttribute('aria-hidden')
          node.removeAttribute('inert')
        })
      }
    }

    nodes.forEach((node) => {
      node.removeAttribute('aria-hidden')
      node.removeAttribute('inert')
    })

    if (wasMoreSheetOpenRef.current) {
      wasMoreSheetOpenRef.current = false
      moreButtonRef.current?.focus()
    }
  }, [isMobile, isMoreSheetOpen])

  useEffect(() => {
    if (!isMobile || !isDetailRoute(location.pathname)) return

    let tracking = false
    let startX = 0
    let startY = 0
    let fired = false

    const onStart = (event: TouchEvent) => {
      const point = event.touches[0]
      if (!point) return
      if (point.clientX > 24) return
      tracking = true
      fired = false
      startX = point.clientX
      startY = point.clientY
    }

    const onMove = (event: TouchEvent) => {
      if (!tracking || fired) return
      const point = event.touches[0]
      if (!point) return
      const dx = point.clientX - startX
      const dy = point.clientY - startY
      if (dx > 72 && Math.abs(dy) < 44) {
        fired = true
        tracking = false
        window.history.back()
      }
    }

    const onEnd = () => {
      tracking = false
      fired = false
    }

    window.addEventListener('touchstart', onStart, { passive: true })
    window.addEventListener('touchmove', onMove, { passive: true })
    window.addEventListener('touchend', onEnd, { passive: true })
    window.addEventListener('touchcancel', onEnd, { passive: true })

    return () => {
      window.removeEventListener('touchstart', onStart)
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('touchend', onEnd)
      window.removeEventListener('touchcancel', onEnd)
    }
  }, [isMobile, location.pathname])

  useEffect(() => {
    if (hideNav || isUnauthed) return

    const AudioCtor = window.AudioContext || (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioCtor) return

    const primeAudio = () => {
      try {
        if (!audioCtxRef.current) audioCtxRef.current = new AudioCtor()
        if (audioCtxRef.current.state === 'suspended') void audioCtxRef.current.resume()
      } catch {
        // ignore autoplay / device restrictions
      }
    }

    window.addEventListener('pointerdown', primeAudio, { passive: true })
    window.addEventListener('keydown', primeAudio)
    return () => {
      window.removeEventListener('pointerdown', primeAudio)
      window.removeEventListener('keydown', primeAudio)
    }
  }, [hideNav, isUnauthed])

  const showAmbientBackground =
    !isMobile && AMBIENT_BACKGROUND_ROUTES.includes(normalizePathname(location.pathname))

  useEffect(() => {
    if (isMobile || !showAmbientBackground) return
    const state = bubbleStateRef.current
    let destroyed = false
    const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
    const scene = document.querySelector<HTMLElement>('.background-scene')
    const popFx: BubblePopFx | null = !prefersReducedMotion && scene ? createBubblePopFx(scene) : null

    const isInteractiveTarget = (target: EventTarget | null) => {
      if (!(target instanceof Element)) return false
      return Boolean(
        target.closest(
          [
            'button',
            'a',
            'input',
            'select',
            'textarea',
            '[role="button"]',
            '.ui-btn',
            '.vision-nav__item',
            '.app-profile-pill',
          ].join(','),
        ),
      )
    }

    const refreshLayers = () => {
      state.layers.layer1 = Array.from(
        document.querySelectorAll<HTMLSpanElement>('.background-scene .layer-1 .bubble'),
      )
      state.layers.layer2 = Array.from(
        document.querySelectorAll<HTMLSpanElement>('.background-scene .layer-2 .bubble'),
      )
      state.layers.layer3 = Array.from(
        document.querySelectorAll<HTMLSpanElement>('.background-scene .layer-3 .bubble'),
      )
    }

    const hitTestBubble = (bubble: HTMLSpanElement, x: number, y: number) => {
      const rect = bubble.getBoundingClientRect()
      if (rect.width <= 0 || rect.height <= 0) return false
      if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) return false

      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const r = Math.min(rect.width, rect.height) / 2
      const dx = x - cx
      const dy = y - cy
      return dx * dx + dy * dy <= r * r
    }

    const findBubbleAt = (x: number, y: number) => {
      // Prefer the front layer when bubbles overlap.
      const layers = [state.layers.layer3, state.layers.layer2, state.layers.layer1]
      for (const layer of layers) {
        for (const bubble of layer) {
          if (bubble.dataset.popping === '1') continue
          if (hitTestBubble(bubble, x, y)) return bubble
        }
      }
      return null
    }

    const setHovered = (bubble: HTMLSpanElement | null) => {
      if (state.hovered === bubble) return
      if (state.hovered) state.hovered.classList.remove('is-hovered')
      state.hovered = bubble
      if (state.hovered) state.hovered.classList.add('is-hovered')
    }

    const respawnBubble = (bubble: HTMLSpanElement) => {
      const clone = bubble.cloneNode(true) as HTMLSpanElement
      clone.classList.remove('is-hovered', 'is-popping', 'is-hidden')
      delete clone.dataset.popping

      bubble.replaceWith(clone)

      const layers = [state.layers.layer1, state.layers.layer2, state.layers.layer3]
      for (const layer of layers) {
        const idx = layer.indexOf(bubble)
        if (idx !== -1) {
          layer[idx] = clone
          break
        }
      }
    }

    const popBubble = (bubble: HTMLSpanElement, clientX?: number, clientY?: number) => {
      if (bubble.dataset.popping === '1') return

      // Make each pop feel slightly different and originate from the actual tap point.
      const rect = bubble.getBoundingClientRect()
      let originX = 0.5
      let originY = 0.5
      if (typeof clientX === 'number' && typeof clientY === 'number' && rect.width > 0 && rect.height > 0) {
        originX = clamp01((clientX - rect.left) / rect.width)
        originY = clamp01((clientY - rect.top) / rect.height)
      }

      // Canvas water-like pop (more organic than CSS-only sprays).
      if (popFx && rect.width > 0 && rect.height > 0) {
        const px = rect.left + rect.width * originX
        const py = rect.top + rect.height * originY
        const r = Math.min(rect.width, rect.height) / 2
        popFx.pop({ x: px, y: py, r, biasX: originX - 0.5, biasY: originY - 0.5 })
      }

      const rot = Math.round(Math.random() * 360)
      const rotEnd = rot + (Math.random() < 0.5 ? -1 : 1) * (12 + Math.random() * 28)
      const shiftX = Math.round((originX - 0.5) * 22 + (Math.random() * 10 - 5))
      const shiftY = Math.round((originY - 0.5) * 22 + (Math.random() * 10 - 5))

      bubble.style.setProperty('--pop-origin-x', `${(originX * 100).toFixed(1)}%`)
      bubble.style.setProperty('--pop-origin-y', `${(originY * 100).toFixed(1)}%`)
      bubble.style.setProperty('--pop-rot', `${rot}deg`)
      bubble.style.setProperty('--pop-rot-end', `${rotEnd}deg`)
      bubble.style.setProperty('--pop-shift-x', `${shiftX}px`)
      bubble.style.setProperty('--pop-shift-y', `${shiftY}px`)

      bubble.dataset.popping = '1'
      bubble.classList.remove('is-hovered')
      bubble.classList.add('is-popping')

      const popMs = 420
      const respawnDelay = 900 + Math.round(Math.random() * 1400)

      const t1 = window.setTimeout(() => {
        if (destroyed) return
        bubble.classList.remove('is-popping')
        bubble.classList.add('is-hidden')
        const t2 = window.setTimeout(() => {
          if (destroyed) return
          respawnBubble(bubble)
        }, respawnDelay)
        state.timers.push(t2)
      }, popMs)
      state.timers.push(t1)
    }

    const onPointerMove = (event: PointerEvent) => {
      state.lastX = event.clientX
      state.lastY = event.clientY
      if (state.moveRaf != null) return
      state.moveRaf = window.requestAnimationFrame(() => {
        state.moveRaf = null
        if (destroyed) return
        setHovered(findBubbleAt(state.lastX, state.lastY))
      })
    }

    const onPointerDown = (event: PointerEvent) => {
      // Only primary click (mouse) or any tap (touch/pen).
      if (event.pointerType === 'mouse' && event.button !== 0) return
      if (isInteractiveTarget(event.target)) return

      const bubble = findBubbleAt(event.clientX, event.clientY)
      if (!bubble) return
      popBubble(bubble, event.clientX, event.clientY)
    }

    refreshLayers()
    window.addEventListener('pointermove', onPointerMove, { passive: true })
    window.addEventListener('pointerdown', onPointerDown, { passive: true })

    return () => {
      destroyed = true
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerdown', onPointerDown)
      popFx?.destroy()
      if (state.moveRaf != null) {
        window.cancelAnimationFrame(state.moveRaf)
        state.moveRaf = null
      }
      setHovered(null)
      for (const timer of state.timers) window.clearTimeout(timer)
      state.timers = []
    }
  }, [isMobile, showAmbientBackground])

  useEffect(() => {
    if (hideNav || isUnauthed) {
      setChatUnreadCount(0)
      return
    }
    if (!principalType || typeof principalId !== 'number') return

    let isActive = true
    let since = new Date().toISOString()
    let controller: AbortController | null = null

    const toast = (title: string, preview: string, unreadCount: number) => {
      setChatToast({ title, preview, unreadCount })
      if (chatToastTimerRef.current != null) window.clearTimeout(chatToastTimerRef.current)
      chatToastTimerRef.current = window.setTimeout(() => setChatToast(null), 5600)
    }

    const playAlert = () => {
      try {
        const AudioCtor = window.AudioContext || (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (!AudioCtor) return
        if (!audioCtxRef.current) audioCtxRef.current = new AudioCtor()
        const ctx = audioCtxRef.current
        if (ctx.state === 'suspended') void ctx.resume()

        const master = ctx.createGain()
        master.gain.setValueAtTime(0.0001, ctx.currentTime)
        master.gain.linearRampToValueAtTime(0.16, ctx.currentTime + 0.02)
        master.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.86)
        master.connect(ctx.destination)

        const scheduleTone = (
          frequency: number,
          startOffset: number,
          duration: number,
          type: OscillatorType,
          volume: number,
        ) => {
          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          const startAt = ctx.currentTime + startOffset
          osc.type = type
          osc.frequency.setValueAtTime(frequency, startAt)
          gain.gain.setValueAtTime(0.0001, startAt)
          gain.gain.linearRampToValueAtTime(volume, startAt + 0.025)
          gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration)
          osc.connect(gain)
          gain.connect(master)
          osc.start(startAt)
          osc.stop(startAt + duration + 0.03)
        }

        scheduleTone(740, 0, 0.18, 'triangle', 0.22)
        scheduleTone(1110, 0.02, 0.16, 'sine', 0.12)
        scheduleTone(988, 0.24, 0.22, 'triangle', 0.2)
        scheduleTone(1480, 0.28, 0.18, 'sine', 0.1)
        scheduleTone(1244, 0.52, 0.28, 'triangle', 0.18)
      } catch {
        // ignore autoplay / device restrictions
      }

      try {
        navigator.vibrate?.([120, 70, 180])
      } catch {
        // ignore unsupported devices
      }
    }

    const previewFor = (thread: ThreadItem) => {
      const last = thread.last_message
      if (!last) return 'Нет сообщений'
      if (last.text && last.text.trim()) return last.text.trim()
      return 'Сообщение'
    }

    const unreadTotal = (threads: ThreadItem[] = []) =>
      threads.reduce((sum, thread) => sum + (Number(thread.unread_count) || 0), 0)

    const loop = async () => {
      // Baseline: load once without notifications to avoid beeping on existing unread.
      try {
        const initial = await apiFetch<ThreadsPayload>('/candidate-chat/threads')
        queryClient.setQueryData(['candidate-chat-threads'], initial)
        setChatUnreadCount(unreadTotal(initial.threads || []))
        since = initial.latest_event_at || since
        const seen: Record<number, string> = {}
        ;(initial.threads || []).forEach((t) => {
          const lastAt = t.last_message_at || t.last_message?.created_at
          if (lastAt) seen[t.id] = lastAt
        })
        chatLastSeenRef.current = seen
        chatInitializedRef.current = true
      } catch {
        // Keep polling anyway; the first successful update will initialize baseline.
      }

      while (isActive) {
        controller = new AbortController()
        try {
          const params = new URLSearchParams()
          if (since) params.set('since', since)
          params.set('timeout', '25')
          const payload = await apiFetch<ThreadsPayload>(`/candidate-chat/threads/updates?${params.toString()}`, {
            signal: controller.signal,
          })

          if (payload.latest_event_at) since = payload.latest_event_at

          if (payload.updated) {
            queryClient.setQueryData(['candidate-chat-threads'], payload)
            const nextUnreadCount = unreadTotal(payload.threads)
            setChatUnreadCount(nextUnreadCount)

            const prevSeen = chatLastSeenRef.current || {}
            const nextSeen: Record<number, string> = { ...prevSeen }
            const newIncoming: Array<{ thread: ThreadItem; at: string }> = []

            for (const thread of payload.threads) {
              const lastAt = thread.last_message_at || thread.last_message?.created_at
              if (!lastAt) continue
              const prevAt = prevSeen[thread.id]
              nextSeen[thread.id] = lastAt

              // Don't notify on baseline load; only for actual new events after init.
              if (!chatInitializedRef.current) continue
              if (prevAt && lastAt <= prevAt) continue

              if (thread.last_message?.direction === 'inbound') {
                newIncoming.push({ thread, at: lastAt })
              }
            }

            chatLastSeenRef.current = nextSeen
            chatInitializedRef.current = true

            if (newIncoming.length) {
              newIncoming.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
              const top = newIncoming[0].thread
              toast(top.title || 'Чат', previewFor(top), nextUnreadCount)
              playAlert()

              // Optional OS notification if already granted (no permission prompts).
              if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
                try {
                  new Notification(`Новое сообщение: ${top.title || 'Чат'}`, { body: previewFor(top) })
                } catch {
                  // ignore
                }
              }
            }
          }
        } catch (err) {
          if ((err as Error).name !== 'AbortError') {
            await new Promise((resolve) => setTimeout(resolve, 1200))
          }
        }
      }
    }

    loop()
    return () => {
      isActive = false
      controller?.abort()
      if (chatToastTimerRef.current != null) {
        window.clearTimeout(chatToastTimerRef.current)
        chatToastTimerRef.current = null
      }
    }
  }, [hideNav, isUnauthed, principalType, principalId])

  if (isUnauthed && !hideNav) {
    return (
      <div className="root-auth-panel">
        <main>
          <div className="glass ui-surface ui-surface--raised root-auth-panel__card">
            <h1 className="root-auth-panel__title">Требуется вход</h1>
            <p className="root-auth-panel__text">
              Сессия не активна. Перейдите на страницу авторизации, чтобы продолжить работу.
            </p>
            <div className="root-auth-panel__actions">
              <Link to="/app/login" className="ui-link">
                Открыть вход
              </Link>
              <a href="/auth/login?redirect_to=/app" className="ui-link">
                Вход (прямой линк)
              </a>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const simulatorEnabled =
    String(import.meta.env.VITE_SIMULATOR_ENABLED || (import.meta.env.DEV ? 'true' : 'false')).toLowerCase() ===
    'true'
  const navItems = buildNavItems({ principalType, simulatorEnabled, icons: ICONS })

  const mobilePrimaryTabs = navItems.slice(0, MOBILE_PRIMARY_TABS)
  const mobileMoreItems = navItems.slice(MOBILE_PRIMARY_TABS)
  const desktopNavItems = navItems.filter((item) => item.to !== '/app/profile')
  const mobileTitle = getMobileTitle(location.pathname)
  const showMobileBack = isDetailRoute(location.pathname)

  return (
    <div className={`app-shell ${showAmbientBackground ? 'app-shell--ambient' : 'app-shell--quiet'}`}>
      {showAmbientBackground && (
        <div className="background-scene" aria-hidden="true">
          <div className="bubbles-layer layer-1">
            <span className="bubble"><span className="bubble__core" /></span>
            <span className="bubble"><span className="bubble__core" /></span>
            <span className="bubble"><span className="bubble__core" /></span>
          </div>
          <div className="bubbles-layer layer-2">
            <span className="bubble"><span className="bubble__core" /></span>
            <span className="bubble"><span className="bubble__core" /></span>
            <span className="bubble"><span className="bubble__core" /></span>
            <span className="bubble"><span className="bubble__core" /></span>
          </div>
          <div className="bubbles-layer layer-3">
            <span className="bubble"><span className="bubble__core" /></span>
            <span className="bubble"><span className="bubble__core" /></span>
          </div>
        </div>
      )}
      {!hideNav && isMobile && (
        <header className="mobile-header glass" aria-label="Мобильный заголовок">
          <button
            type="button"
            className="mobile-header__back ui-btn ui-btn--ghost ui-btn--sm"
            onClick={() => window.history.back()}
            aria-hidden={!showMobileBack}
            tabIndex={showMobileBack ? 0 : -1}
          >
            ←
          </button>
          <div className="mobile-header__title">{mobileTitle}</div>
          <Link to="/app/profile" className="mobile-header__profile" title="Профиль">
            {ICONS.profile}
          </Link>
        </header>
      )}
      {!hideNav && (
        <header className="app-header">
          <div className="app-header-left" />

          <nav className="vision-nav-pill ui-surface ui-surface--raised" aria-label="Основная навигация">
            {desktopNavItems.map((item) => {
              const isChatTab = item.to === '/app/messenger'
              const hasUnread = isChatTab && chatUnreadCount > 0
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`vision-nav__item${hasUnread ? ' has-alert' : ''}`}
                  activeProps={{ className: `vision-nav__item is-active${hasUnread ? ' has-alert' : ''}` }}
                  data-tone={item.tone}
                  title={item.label}
                >
                  <span className="vision-nav__icon">{item.icon}</span>
                  <span className="vision-nav__label">{item.label}</span>
                  {hasUnread && <span className="vision-nav__alert-dot" aria-hidden="true" />}
                  {hasUnread && (
                    <span className="vision-nav__badge" aria-label={`${chatUnreadCount} непрочитанных сообщений`}>
                      {chatUnreadCount > 99 ? '99+' : chatUnreadCount}
                    </span>
                  )}
                </Link>
              )
            })}
          </nav>

          <div className="app-header-right">
            <Link to="/app/profile" className="app-profile-pill ui-surface ui-surface--raised" title="Профиль">
              <span className="app-profile__icon">{ICONS.profile}</span>
            </Link>
          </div>
        </header>
      )}
      <main
        className={`app-main${isMobile ? ` mobile-route-transition mobile-route-transition--${mobileTransition}` : ''}`}
      >
        <Outlet />
      </main>
      {!hideNav && isMobile && (
        <>
          <nav className="mobile-tab-bar glass" aria-label="Мобильная навигация">
            {mobilePrimaryTabs.map((item) => {
              const active = isPathActive(location.pathname, item.to)
              const isChatTab = item.to === '/app/messenger'
              const hasUnread = isChatTab && chatUnreadCount > 0
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`mobile-tab-item ${active ? 'is-active' : ''}${hasUnread ? ' has-alert' : ''}`}
                  data-tone={item.tone}
                  title={item.label}
                >
                  <span className="mobile-tab-item__icon">{item.icon}</span>
                  <span className="mobile-tab-item__label">{item.label}</span>
                  {isChatTab && chatUnreadCount > 0 && (
                    <>
                      <span className="mobile-tab-item__signal" aria-hidden="true" />
                      <span className="mobile-tab-item__badge is-alert">{chatUnreadCount > 99 ? '99+' : chatUnreadCount}</span>
                    </>
                  )}
                  <span className="mobile-tab-item__dot" />
                </Link>
              )
            })}
            <button
              type="button"
              className={`mobile-tab-item ${isMoreSheetOpen ? 'is-active' : ''}`}
              onClick={() => setIsMoreSheetOpen((open) => !open)}
              aria-expanded={isMoreSheetOpen}
              aria-controls="mobile-more-sheet"
              title="Ещё"
              ref={moreButtonRef}
            >
              <span className="mobile-tab-item__icon">{ICONS.more}</span>
              <span className="mobile-tab-item__label">Ещё</span>
              <span className="mobile-tab-item__dot" />
            </button>
          </nav>

          {isMoreSheetOpen && (
            <div id="mobile-more-sheet" className="mobile-sheet is-open">
              <button
                type="button"
                className="mobile-sheet__backdrop"
                onClick={() => setIsMoreSheetOpen(false)}
                aria-label="Закрыть меню"
              />
              <div className="mobile-sheet__body glass" role="dialog" aria-modal="true" aria-label="Ещё разделы">
                <div className="mobile-sheet__handle" />
                <div className="mobile-sheet__title">Ещё разделы</div>
                <div className="mobile-sheet__list">
                  {mobileMoreItems.map((item) => (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={`mobile-sheet__item ${isPathActive(location.pathname, item.to) ? 'is-active' : ''}`}
                      onClick={() => setIsMoreSheetOpen(false)}
                    >
                      <span className="mobile-sheet__item-icon">{item.icon}</span>
                      <span>{item.label}</span>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
      {chatToast && (
        <div className="toast chat-toast ui-surface ui-surface--floating" data-tone="warning" role="alert" aria-live="assertive" aria-atomic="true">
          <span className="chat-toast__eyebrow">Новое сообщение</span>
          <div className="chat-toast__header">
            <span className="chat-toast__icon" aria-hidden="true">{ICONS.messenger}</span>
            <div className="chat-toast__copy">
              <strong className="chat-toast__title">{chatToast.title}</strong>
              <span className="chat-toast__preview">{chatToast.preview}</span>
            </div>
            <span className="chat-toast__count">{chatToast.unreadCount > 99 ? '99+' : chatToast.unreadCount}</span>
          </div>
          <span className="chat-toast__hint">Откройте вкладку «Чаты», чтобы ответить кандидату</span>
        </div>
      )}
    </div>
  )
}
