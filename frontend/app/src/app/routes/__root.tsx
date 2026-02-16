import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useProfile } from '@/app/hooks/useProfile'
import { apiFetch, queryClient } from '@/api/client'

type BubblePopFx = {
  pop: (args: { x: number; y: number; r: number; biasX: number; biasY: number }) => void
  destroy: () => void
}

type BubblePopSplash = {
  id: number
  t0: number
  ttl: number
  x: number
  y: number
  r: number
  driftX: number
  driftY: number
  noise: number[]
  glints: Array<{ a0: number; a1: number; ro: number; hue: number; w: number }>
  filaments: Array<{ a: number; len: number; ro: number; hue: number }>
  droplets: Array<{
    t0: number
    ttl: number
    x: number
    y: number
    vx: number
    vy: number
    size: number
  }>
}

const TAU = Math.PI * 2

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const clamp01 = (value: number) => clamp(value, 0, 1)
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const smoothstep01 = (t: number) => {
  const x = clamp01(t)
  return x * x * (3 - 2 * x)
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - clamp01(t), 3)
const easeOutQuint = (t: number) => 1 - Math.pow(1 - clamp01(t), 5)

const randRange = (min: number, max: number) => min + Math.random() * (max - min)
const randInt = (min: number, max: number) => Math.floor(randRange(min, max + 1))

const sampleNoiseLoop = (noise: number[], at: number) => {
  const n = noise.length
  if (!n) return 0
  const x = ((at % n) + n) % n
  const i0 = Math.floor(x)
  const i1 = (i0 + 1) % n
  const t = x - i0
  return lerp(noise[i0]!, noise[i1]!, smoothstep01(t))
}

function createBubblePopFx(container: HTMLElement): BubblePopFx {
  const canvas = document.createElement('canvas')
  canvas.className = 'bubble-popfx-canvas'
  container.appendChild(canvas)

  const ctx = canvas.getContext('2d', { alpha: true })
  if (!ctx) {
    return {
      pop: () => {},
      destroy: () => {
        canvas.remove()
      },
    }
  }

  let destroyed = false
  let raf: number | null = null
  let seq = 0
  const splashes: BubblePopSplash[] = []

  let dpr = 1

  const resize = () => {
    const nextDpr = Math.min(2, window.devicePixelRatio || 1)
    dpr = nextDpr
    const w = Math.max(1, Math.round(window.innerWidth * dpr))
    const h = Math.max(1, Math.round(window.innerHeight * dpr))
    if (canvas.width !== w) canvas.width = w
    if (canvas.height !== h) canvas.height = h
    canvas.style.width = `${window.innerWidth}px`
    canvas.style.height = `${window.innerHeight}px`
  }

  resize()
  window.addEventListener('resize', resize, { passive: true })

  const clearCanvas = () => {
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }

  const drawSplash = (s: BubblePopSplash, now: number) => {
    const t = (now - s.t0) / s.ttl
    if (t >= 1) return
    const e = easeOutQuint(t)
    const fade = 1 - e

    // Slight drift makes the tear feel more organic and less "vector-perfect".
    const cx = s.x + s.driftX * e
    const cy = s.y + s.driftY * e

    // A tiny mist puff near the puncture point.
    {
      const mistR = s.r * (0.28 + 0.85 * e)
      const mistA = fade * 0.12
      if (mistA > 0.001) {
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, mistR)
        g.addColorStop(0, `rgba(210, 250, 255, ${mistA})`)
        g.addColorStop(1, `rgba(210, 250, 255, 0)`)
        ctx.fillStyle = g
        ctx.beginPath()
        ctx.arc(cx, cy, mistR, 0, TAU)
        ctx.fill()
      }
    }

    // Irregular ripple ring (soap film / water tension vibe).
    const baseR = s.r * (0.18 + 1.35 * e)
    const wobble = fade * s.r * 0.17
    const thickness = clamp(fade * (4.8 + s.r * 0.04), 0.9, 10)

    ctx.save()
    ctx.globalCompositeOperation = 'screen'
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    // Under-stroke: soft cyan water body.
    ctx.strokeStyle = `rgba(140, 235, 255, ${fade * 0.26})`
    ctx.lineWidth = thickness * 1.05
    ctx.beginPath()
    {
      const steps = 64
      const swirl = e * 7.5
      for (let i = 0; i <= steps; i++) {
        const a = (i / steps) * TAU
        const n = sampleNoiseLoop(s.noise, i * 0.85 + swirl) + Math.sin(a * 5 + s.id * 0.7) * 0.22
        const rr = baseR + n * wobble
        const x = cx + Math.cos(a) * rr
        const y = cy + Math.sin(a) * rr
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
    }
    ctx.stroke()

    // Glints: non-uniform, iridescent highlights (breaks "sunburst" symmetry).
    for (const g of s.glints) {
      const glintA = fade * 0.32
      if (glintA <= 0.001) continue
      const hue = (g.hue + e * 120) % 360
      ctx.strokeStyle = `hsla(${hue.toFixed(1)}, 85%, 78%, ${glintA.toFixed(3)})`
      ctx.lineWidth = thickness * g.w
      ctx.beginPath()
      ctx.arc(cx, cy, baseR + g.ro * (0.4 + 0.6 * fade), g.a0, g.a1)
      ctx.stroke()
    }

    // Filaments: tiny tear strands around the ring.
    for (const f of s.filaments) {
      const fa = fade * 0.22
      if (fa <= 0.001) continue
      const hue = (f.hue + e * 80) % 360
      const a = f.a
      const rr = baseR + f.ro * fade
      const x0 = cx + Math.cos(a) * rr
      const y0 = cy + Math.sin(a) * rr
      const x1 = cx + Math.cos(a) * (rr + f.len * (0.6 + 0.4 * fade))
      const y1 = cy + Math.sin(a) * (rr + f.len * (0.6 + 0.4 * fade))
      ctx.strokeStyle = `hsla(${hue.toFixed(1)}, 80%, 80%, ${fa.toFixed(3)})`
      ctx.lineWidth = thickness * 0.22
      ctx.beginPath()
      ctx.moveTo(x0, y0)
      ctx.lineTo(x1, y1)
      ctx.stroke()
    }

    // Droplets: small water beads with slight motion streaks.
    for (const d of s.droplets) {
      const pt = (now - d.t0) / d.ttl
      if (pt >= 1) continue
      const de = easeOutCubic(pt)
      const da = (1 - de) * 0.75
      if (da <= 0.001) continue

      // Predict current position (integrated in tick, but this keeps draw independent if dt jitters).
      const dx = d.x
      const dy = d.y
      const speed = Math.hypot(d.vx, d.vy)
      const nx = speed > 0.001 ? d.vx / speed : 0
      const ny = speed > 0.001 ? d.vy / speed : 0
      const streak = clamp(speed * 0.012, 0, 10)

      ctx.globalAlpha = da
      ctx.strokeStyle = 'rgba(200, 250, 255, 0.35)'
      ctx.lineWidth = Math.max(0.7, d.size * 0.42)
      ctx.beginPath()
      ctx.moveTo(dx, dy)
      ctx.lineTo(dx - nx * streak, dy - ny * streak)
      ctx.stroke()

      ctx.fillStyle = 'rgba(170, 240, 255, 0.65)'
      ctx.shadowBlur = d.size * 3.2
      ctx.shadowColor = 'rgba(120, 220, 255, 0.25)'
      ctx.beginPath()
      ctx.arc(dx, dy, d.size, 0, TAU)
      ctx.fill()

      ctx.shadowBlur = 0
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
      ctx.beginPath()
      ctx.arc(dx - d.size * 0.25, dy - d.size * 0.25, d.size * 0.32, 0, TAU)
      ctx.fill()
    }

    ctx.restore()

    // Reset state potentially mutated by droplet shadows.
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
    ctx.globalCompositeOperation = 'source-over'
  }

  let lastNow = 0
  const tick = (now: number) => {
    if (destroyed) return
    if (!lastNow) lastNow = now
    const dt = clamp((now - lastNow) / 1000, 0, 0.05)
    lastNow = now

    // Update droplets with a light drag+gravity to avoid overly ballistic motion.
    const drag = 4.8
    const gravity = 720
    for (const s of splashes) {
      for (const d of s.droplets) {
        const t = (now - d.t0) / d.ttl
        if (t >= 1) continue
        const k = Math.exp(-drag * dt)
        d.vx *= k
        d.vy = d.vy * k + gravity * dt
        d.x += d.vx * dt
        d.y += d.vy * dt
      }
    }

    // Remove finished splashes.
    for (let i = splashes.length - 1; i >= 0; i--) {
      const s = splashes[i]!
      if (now - s.t0 >= s.ttl) splashes.splice(i, 1)
    }

    clearCanvas()
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    for (const s of splashes) drawSplash(s, now)

    if (splashes.length) raf = window.requestAnimationFrame(tick)
    else raf = null
  }

  const ensureLoop = () => {
    if (raf != null) return
    lastNow = 0
    raf = window.requestAnimationFrame(tick)
  }

  const pop = (args: { x: number; y: number; r: number; biasX: number; biasY: number }) => {
    const now = performance.now()
    const r = clamp(args.r, 18, 180)

    const biasAngle = Math.atan2(args.biasY, args.biasX) + randRange(-0.35, 0.35)
    const driftMag = r * randRange(0.06, 0.18)
    const driftX = Math.cos(biasAngle) * driftMag * randRange(0.5, 1)
    const driftY = Math.sin(biasAngle) * driftMag * randRange(0.5, 1)

    // Value-noise table for the ring wobble (looping).
    const noise = Array.from({ length: 48 }, () => randRange(-1, 1))

    // Glints are precomputed uneven arc spans to avoid "sun ray" symmetry.
    const glints = Array.from({ length: randInt(6, 10) }, () => {
      const a0 = randRange(-Math.PI, Math.PI)
      const span = randRange(0.18, 0.6)
      const a1 = a0 + span
      return {
        a0,
        a1,
        ro: randRange(-r * 0.08, r * 0.14),
        hue: randRange(175, 205) + randRange(-28, 34),
        w: randRange(0.25, 0.55),
      }
    })

    const filaments = Array.from({ length: randInt(10, 16) }, () => ({
      a: randRange(-Math.PI, Math.PI),
      len: r * randRange(0.06, 0.18),
      ro: randRange(-r * 0.06, r * 0.12),
      hue: randRange(160, 215) + randRange(-30, 40),
    }))

    // Droplets: 3 irregular clusters => organic "burst", not perfect radial spread.
    const clusters = randInt(2, 4)
    const clusterAngles = Array.from({ length: clusters }, (_, i) => biasAngle + (i - (clusters - 1) / 2) * randRange(0.9, 1.35))
    const clusterSpread = randRange(0.38, 0.7)
    const dropletCount = clamp(Math.round(14 + (r / 70) * 18 + randRange(-3, 6)), 14, 38)

    const droplets: BubblePopSplash['droplets'] = []
    for (let i = 0; i < dropletCount; i++) {
      const ci = randInt(0, clusters - 1)
      const theta = (clusterAngles[ci] ?? biasAngle) + randRange(-clusterSpread, clusterSpread) * (0.6 + 0.7 * Math.random())
      const speed = (160 + r * 6.2) * randRange(0.38, 0.95)
      const size = randRange(0.9, 2.6) + r * randRange(0.001, 0.004)

      const vx = Math.cos(theta) * speed
      const vy = Math.sin(theta) * speed - randRange(60, 140)

      droplets.push({
        t0: now,
        ttl: randRange(420, 820),
        x: args.x + randRange(-r * 0.02, r * 0.02),
        y: args.y + randRange(-r * 0.02, r * 0.02),
        vx,
        vy,
        size,
      })
    }

    splashes.push({
      id: ++seq,
      t0: now,
      ttl: randRange(720, 980),
      x: args.x,
      y: args.y,
      r,
      driftX,
      driftY,
      noise,
      glints,
      filaments,
      droplets,
    })

    ensureLoop()
  }

  return {
    pop,
    destroy: () => {
      destroyed = true
      if (raf != null) window.cancelAnimationFrame(raf)
      raf = null
      window.removeEventListener('resize', resize)
      canvas.remove()
    },
  }
}

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
  copilot: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2l1.4 6.2L20 10l-6.6 1.8L12 18l-1.4-6.2L4 10l6.6-1.8L12 2z" />
      <path d="M5 20l1-3" />
      <path d="M19 20l-1-3" />
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

  const simulatorEnabled =
    String(import.meta.env.VITE_SIMULATOR_ENABLED || (import.meta.env.DEV ? 'true' : 'false')).toLowerCase() ===
    'true'
  const navItems =
    principalType === 'recruiter'
      ? [
          { to: '/app/dashboard', label: 'Дашборд', icon: ICONS.dashboard, tone: 'blue' },
          { to: '/app/slots', label: 'Слоты', icon: ICONS.slots, tone: 'violet' },
          { to: '/app/candidates', label: 'Кандидаты', icon: ICONS.candidates, tone: 'sky' },
          { to: '/app/messenger', label: 'Чаты', icon: ICONS.messenger, tone: 'aqua' },
          { to: '/app/copilot', label: 'Copilot', icon: ICONS.copilot, tone: 'amber' },
        ]
      : principalType === 'admin'
        ? [
            { to: '/app/dashboard', label: 'Дашборд', icon: ICONS.dashboard, tone: 'blue' },
            { to: '/app/slots', label: 'Слоты', icon: ICONS.slots, tone: 'violet' },
            { to: '/app/candidates', label: 'Кандидаты', icon: ICONS.candidates, tone: 'sky' },
            { to: '/app/recruiters', label: 'Рекрутёры', icon: ICONS.recruiters, tone: 'indigo' },
            { to: '/app/cities', label: 'Города', icon: ICONS.cities, tone: 'sunset' },
            { to: '/app/messenger', label: 'Чаты', icon: ICONS.messenger, tone: 'aqua' },
            { to: '/app/copilot', label: 'Copilot', icon: ICONS.copilot, tone: 'amber' },
            ...(simulatorEnabled ? [{ to: '/app/simulator', label: 'Симулятор', icon: ICONS.slots, tone: 'violet' }] : []),
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
