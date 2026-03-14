import { motion, useReducedMotion } from 'framer-motion'

type RatingScaleProps = {
  value: number | null
  onChange: (value: number) => void
}

const SCALE_LABELS = ['😐 1', '🙂 2', '😊 3', '🤩 4', '⭐ 5']

export default function RatingScale({ value, onChange }: RatingScaleProps) {
  const reduceMotion = useReducedMotion()

  return (
    <div className="interview-script__rating" role="radiogroup" aria-label="Оценка ответа">
      {SCALE_LABELS.map((label, index) => {
        const rating = index + 1
        const active = value === rating
        return (
          <motion.button
            key={label}
            type="button"
            className={`interview-script__rating-item ${active ? 'interview-script__rating-item--active' : ''}`}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(rating)}
            whileTap={reduceMotion ? undefined : { scale: 0.96 }}
            animate={
              reduceMotion || !active
                ? undefined
                : {
                    scale: [1, 1.14, 1],
                    transition: { duration: 0.2, ease: [0.25, 0.1, 0.25, 1] },
                  }
            }
          >
            {label}
          </motion.button>
        )
      })}
    </div>
  )
}
