import { listItem, motionDurations, motionEaseOut, motionEaseSpring, slideUp } from '@/shared/motion'

export const pipelineMotion = {
  stagger: 0.05,
  cardDuration: motionDurations.base,
  railDuration: motionDurations.slow,
  hoverDuration: motionDurations.fast,
  expandDuration: 0.3,
  pulseDuration: 2,
  glowDuration: 3,
  easing: motionEaseOut,
  spring: { stiffness: 300, damping: 30 },
} as const

export const pipelineCardVariants = {
  hidden: listItem.initial,
  visible: (index: number) => ({
    ...listItem.animate,
    transition: {
      delay: index * pipelineMotion.stagger,
      duration: pipelineMotion.cardDuration,
      ease: motionEaseSpring,
    },
  }),
}

export const pipelinePanelVariants = {
  hidden: { ...slideUp.initial, height: 0 },
  visible: {
    ...slideUp.animate,
    height: 'auto',
    transition: {
      duration: pipelineMotion.expandDuration,
      ease: motionEaseSpring,
    },
  },
  exit: {
    ...slideUp.exit,
    height: 0,
    transition: {
      duration: 0.22,
      ease: motionEaseOut,
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
      ease: motionEaseSpring,
    },
  }),
}
