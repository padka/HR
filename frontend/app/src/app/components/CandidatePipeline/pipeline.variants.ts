export const pipelineMotion = {
  stagger: 0.1,
  cardDuration: 0.45,
  railDuration: 0.8,
  hoverDuration: 0.15,
  expandDuration: 0.3,
  pulseDuration: 2,
  glowDuration: 3,
  easing: [0.25, 0.1, 0.25, 1.0] as const,
  spring: { stiffness: 300, damping: 30 },
} as const

export const pipelineCardVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.95 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      delay: index * pipelineMotion.stagger,
      duration: pipelineMotion.cardDuration,
      ease: pipelineMotion.easing,
    },
  }),
}

export const pipelinePanelVariants = {
  hidden: { opacity: 0, height: 0, y: -12 },
  visible: {
    opacity: 1,
    height: 'auto',
    y: 0,
    transition: {
      duration: pipelineMotion.expandDuration,
      ease: pipelineMotion.easing,
    },
  },
  exit: {
    opacity: 0,
    height: 0,
    y: -12,
    transition: {
      duration: 0.22,
      ease: pipelineMotion.easing,
    },
  },
}

export const pipelineRailVariants = {
  hidden: { scaleX: 0, scaleY: 0 },
  visible: (axis: 'x' | 'y') => ({
    scaleX: axis === 'x' ? 1 : 1,
    scaleY: axis === 'y' ? 1 : 1,
    transition: {
      duration: pipelineMotion.railDuration,
      ease: pipelineMotion.easing,
    },
  }),
}
