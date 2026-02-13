import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useProfile } from '@/app/hooks/useProfile'
import { apiFetch, queryClient } from '@/api/client'

type ThreadItem = {
  id: number
  type: 'direct' | 'group'
  title: string
  created_at: string
  last_message?: {
    text?: string | null
    created_at?: string | null
    sender_type?: string | null
    sender_id?: number | null
    type?: string | null
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
}

export function RootLayout() {
  const { location } = useRouterState()
  const hideNav = location.pathname.startsWith('/app/login')
  const profileQuery = useProfile(!hideNav)
  const principalType = profileQuery.data?.principal.type
  const authError = profileQuery.error as (Error & { status?: number }) | undefined
  const isUnauthed = authError?.status === 401
  const principalId = profileQuery.data?.principal.id

  const [chatToast, setChatToast] = useState<{ title: string; preview: string } | null>(null)
  const chatToastTimerRef = useRef<number | null>(null)
  const chatLastSeenRef = useRef<Record<number, string>>({})
  const chatInitializedRef = useRef(false)
  const audioCtxRef = useRef<AudioContext | null>(null)

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
    const state = bubbleStateRef.current
    let destroyed = false

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

    const popBubble = (bubble: HTMLSpanElement) => {
      if (bubble.dataset.popping === '1') return
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
      popBubble(bubble)
    }

    refreshLayers()
    window.addEventListener('pointermove', onPointerMove, { passive: true })
    window.addEventListener('pointerdown', onPointerDown, { passive: true })

    return () => {
      destroyed = true
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerdown', onPointerDown)
      if (state.moveRaf != null) {
        window.cancelAnimationFrame(state.moveRaf)
        state.moveRaf = null
      }
      setHovered(null)
      for (const timer of state.timers) window.clearTimeout(timer)
      state.timers = []
    }
  }, [])

  useEffect(() => {
    if (hideNav || isUnauthed) return
    if (!principalType || typeof principalId !== 'number') return

    let isActive = true
    let since = new Date().toISOString()
    let controller: AbortController | null = null

    const toast = (title: string, preview: string) => {
      setChatToast({ title, preview })
      if (chatToastTimerRef.current != null) window.clearTimeout(chatToastTimerRef.current)
      chatToastTimerRef.current = window.setTimeout(() => setChatToast(null), 4200)
    }

    const playBeep = () => {
      try {
        const AudioCtor = window.AudioContext || (window as any).webkitAudioContext
        if (!AudioCtor) return
        if (!audioCtxRef.current) audioCtxRef.current = new AudioCtor()
        const ctx = audioCtxRef.current
        if (ctx.state === 'suspended') void ctx.resume()

        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.value = 880
        gain.gain.setValueAtTime(0.0001, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.07, ctx.currentTime + 0.01)
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18)
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.start()
        osc.stop(ctx.currentTime + 0.2)
      } catch {
        // ignore autoplay / device restrictions
      }
    }

    const previewFor = (thread: ThreadItem) => {
      const last = thread.last_message
      if (!last) return 'Нет сообщений'
      if (last.type === 'candidate_task') return 'Передан кандидат'
      if (last.type === 'system') return last.text || 'Системное сообщение'
      if (last.text && last.text.trim()) return last.text.trim()
      return 'Файл'
    }

    const loop = async () => {
      // Baseline: load once without notifications to avoid beeping on existing unread.
      try {
        const initial = await apiFetch<ThreadsPayload>('/staff/threads')
        queryClient.setQueryData(['staff-threads'], initial)
        since = initial.latest_event_at || since
        const seen: Record<number, string> = {}
        ;(initial.threads || []).forEach((t) => {
          const lastAt = t.last_message?.created_at || t.created_at
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
          const payload = await apiFetch<ThreadsPayload>(`/staff/threads/updates?${params.toString()}`, {
            signal: controller.signal,
          })

          if (payload.latest_event_at) since = payload.latest_event_at

          if (payload.updated && payload.threads?.length) {
            queryClient.setQueryData(['staff-threads'], payload)

            const prevSeen = chatLastSeenRef.current || {}
            const nextSeen: Record<number, string> = { ...prevSeen }
            const newIncoming: Array<{ thread: ThreadItem; at: string }> = []

            for (const thread of payload.threads) {
              const lastAt = thread.last_message?.created_at || thread.created_at
              if (!lastAt) continue
              const prevAt = prevSeen[thread.id]
              nextSeen[thread.id] = lastAt

              // Don't notify on baseline load; only for actual new events after init.
              if (!chatInitializedRef.current) continue
              if (prevAt && lastAt <= prevAt) continue

              const senderType = thread.last_message?.sender_type
              const senderId = thread.last_message?.sender_id
              const isSelf = senderType === principalType && senderId === principalId
              if (!isSelf) newIncoming.push({ thread, at: lastAt })
            }

            chatLastSeenRef.current = nextSeen
            chatInitializedRef.current = true

            if (newIncoming.length) {
              newIncoming.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
              const top = newIncoming[0].thread
              toast(top.title || 'Чат', previewFor(top))
              playBeep()

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
      <div style={{ minHeight: '100vh', padding: '24px', display: 'grid', gap: '16px' }}>
        <main>
          <div className="glass" style={{ padding: 24 }}>
            <h1 style={{ marginTop: 0 }}>Требуется вход</h1>
            <p style={{ color: 'var(--muted)' }}>
              Сессия не активна. Перейдите на страницу авторизации, чтобы продолжить работу.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <Link to="/app/login" style={{ textDecoration: 'underline', color: 'var(--fg)' }}>
                Открыть вход
              </Link>
              <a href="/auth/login?redirect_to=/app" style={{ textDecoration: 'underline', color: 'var(--fg)' }}>
                Вход (прямой линк)
              </a>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const navItems =
    principalType === 'recruiter'
      ? [
          { to: '/app/dashboard', label: 'Дашборд', icon: ICONS.dashboard, tone: 'blue' },
          { to: '/app/slots', label: 'Слоты', icon: ICONS.slots, tone: 'violet' },
          { to: '/app/candidates', label: 'Кандидаты', icon: ICONS.candidates, tone: 'sky' },
          { to: '/app/messenger', label: 'Чаты', icon: ICONS.messenger, tone: 'aqua' },
        ]
      : principalType === 'admin'
        ? [
            { to: '/app/dashboard', label: 'Дашборд', icon: ICONS.dashboard, tone: 'blue' },
            { to: '/app/recruiters', label: 'Рекрутёры', icon: ICONS.recruiters, tone: 'indigo' },
            { to: '/app/cities', label: 'Города', icon: ICONS.cities, tone: 'sunset' },
            { to: '/app/messenger', label: 'Чаты', icon: ICONS.messenger, tone: 'aqua' },
            { to: '/app/system', label: 'Бот', icon: ICONS.bot, tone: 'emerald' },
          ]
        : []

  return (
    <div className="app-shell">
      <div className="background-scene">
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
      {!hideNav && (
        <header className="app-header">
          <div className="app-header-left" />
          
          <nav className="vision-nav-pill" aria-label="Основная навигация">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="vision-nav__item"
                activeProps={{ className: 'vision-nav__item is-active' }}
                data-tone={item.tone}
                title={item.label}
              >
                <span className="vision-nav__icon">{item.icon}</span>
                <span className="vision-nav__label">{item.label}</span>
              </Link>
            ))}
          </nav>

          <div className="app-header-right">
            <Link to="/app/profile" className="app-profile-pill glass" title="Профиль">
              <span className="app-profile__icon">{ICONS.profile}</span>
            </Link>
          </div>
        </header>
      )}
      <main>
        <Outlet />
      </main>
      {chatToast && (
        <div className="toast" data-tone="success" style={{ top: 20, right: 20, bottom: 'auto' }}>
          <strong style={{ fontSize: 13 }}>{chatToast.title}</strong>
          <span style={{ color: 'var(--muted)', fontSize: 12, lineHeight: 1.2 }}>{chatToast.preview}</span>
        </div>
      )}
    </div>
  )
}
