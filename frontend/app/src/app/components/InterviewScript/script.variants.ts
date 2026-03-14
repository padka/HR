export const scriptMotion = {
  panelSpring: { type: 'spring' as const, stiffness: 260, damping: 28 },
  easing: [0.25, 0.1, 0.25, 1] as const,
  duration: 0.3,
}

export const scriptPanelVariants = {
  hidden: { opacity: 0, x: 24 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { ...scriptMotion.panelSpring },
  },
  exit: {
    opacity: 0,
    x: 18,
    transition: { duration: scriptMotion.duration, ease: scriptMotion.easing },
  },
}

export const scriptStepVariants = {
  hidden: { opacity: 0, x: 18 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: scriptMotion.duration, ease: scriptMotion.easing },
  },
  exit: {
    opacity: 0,
    x: -18,
    transition: { duration: scriptMotion.duration, ease: scriptMotion.easing },
  },
}

export const scriptScorecardItemVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: index * 0.05,
      duration: 0.24,
      ease: scriptMotion.easing,
    },
  }),
}
