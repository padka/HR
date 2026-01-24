import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/app/')({
  component: () => (
    <div className="glass" style={{ padding: '16px' }}>
      <h1>Новая SPA на React</h1>
      <p>Постепенно переносим все экраны. Перейдите во вкладку «Слоты».</p>
    </div>
  )
})
