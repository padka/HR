import type { InterviewScriptStep } from './script.types'

type ScriptStepperProps = {
  steps: InterviewScriptStep[]
  currentStep: number
  onSelect: (index: number) => void
}

export default function ScriptStepper({ steps, currentStep, onSelect }: ScriptStepperProps) {
  return (
    <div className="interview-script__stepper" role="tablist" aria-label="Шаги интервью">
      {steps.map((step, index) => (
        <button
          key={step.id}
          type="button"
          role="tab"
          aria-selected={index === currentStep}
          aria-label={step.label}
          className={`interview-script__stepper-dot ${index === currentStep ? 'interview-script__stepper-dot--active' : index < currentStep ? 'interview-script__stepper-dot--passed' : ''}`}
          onClick={() => onSelect(index)}
        >
          <span className="interview-script__stepper-index">{index + 1}</span>
        </button>
      ))}
    </div>
  )
}
