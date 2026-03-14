import { listItem, motionDurations, motionEaseOut, motionEaseSpring, slideInRight, slideUp } from '@/shared/motion'

export const scriptMotion = {
  panelSpring: { type: 'spring' as const, stiffness: 260, damping: 28 },
  easing: motionEaseOut,
  duration: motionDurations.base,
}

export const scriptPanelVariants = {
  hidden: slideInRight.initial,
  visible: {
    ...slideInRight.animate,
    transition: { duration: motionDurations.slow, ease: motionEaseSpring },
  },
  exit: {
    ...slideInRight.exit,
    transition: { duration: motionDurations.slow, ease: motionEaseSpring },
  },
}

export const scriptStepVariants = {
  hidden: slideUp.initial,
  visible: {
    ...slideUp.animate,
    transition: { duration: 0.3, ease: motionEaseSpring },
  },
  exit: {
    ...slideUp.exit,
    transition: { duration: motionDurations.base, ease: motionEaseOut },
  },
}

export const scriptScorecardItemVariants = {
  hidden: listItem.initial,
  visible: (index: number) => ({
    ...listItem.animate,
    transition: {
      delay: index * 0.05,
      duration: 0.24,
      ease: motionEaseSpring,
    },
  }),
}
