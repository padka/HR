export const motionEaseOut = [0.25, 0.1, 0.25, 1] as const
export const motionEaseInOut = [0.45, 0, 0.55, 1] as const
export const motionEaseSpring = [0.22, 1, 0.36, 1] as const

export const motionDurations = {
  instant: 0.1,
  fast: 0.15,
  base: 0.25,
  slow: 0.4,
  slower: 0.6,
} as const

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: motionDurations.base, ease: motionEaseOut },
} as const

export const slideUp = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 8 },
  transition: { duration: 0.3, ease: motionEaseSpring },
} as const

export const slideInRight = {
  initial: { x: '100%' },
  animate: { x: 0 },
  exit: { x: '100%' },
  transition: { duration: motionDurations.slow, ease: motionEaseSpring },
} as const

export const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.2, ease: motionEaseSpring },
} as const

export const stagger = (delay = 0.05) => ({
  animate: { transition: { staggerChildren: delay } },
})

export const listItem = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 6 },
  transition: { duration: motionDurations.base, ease: motionEaseSpring },
} as const
