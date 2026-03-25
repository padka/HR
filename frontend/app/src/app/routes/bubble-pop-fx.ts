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

export function createBubblePopFx(container: HTMLElement): BubblePopFx {
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

    const cx = s.x + s.driftX * e
    const cy = s.y + s.driftY * e

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

    const baseR = s.r * (0.18 + 1.35 * e)
    const wobble = fade * s.r * 0.17
    const thickness = clamp(fade * (4.8 + s.r * 0.04), 0.9, 10)

    ctx.save()
    ctx.globalCompositeOperation = 'screen'
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

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

    for (const d of s.droplets) {
      const pt = (now - d.t0) / d.ttl
      if (pt >= 1) continue
      const de = easeOutCubic(pt)
      const da = (1 - de) * 0.75
      if (da <= 0.001) continue

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

    const noise = Array.from({ length: 48 }, () => randRange(-1, 1))

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

export type { BubblePopFx }
