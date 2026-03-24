import type { AISummary, TestQuestionAnswer, TestSection } from '@/api/services/candidates'

export type ScriptBlock =
  | { type: 'speech'; text: string }
  | { type: 'prompt'; text: string }
  | { type: 'note'; text: string }
  | { type: 'ai-hint'; icon: string; label: string; text: string }
  | { type: 'branch'; condition: string; options: { label: string; text: string }[] }
  | { type: 'divider' }

export type ScriptSection = {
  id: string
  step: number
  title: string
  duration?: string
  blocks: ScriptBlock[]
}

function shorten(value: string | null | undefined, limit = 100) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.length <= limit) return text
  return `${text.slice(0, Math.max(0, limit - 1)).trim()}…`
}

function questionWeight(answer: TestQuestionAnswer) {
  let score = 0
  if (answer.is_correct === false) score += 3
  if (answer.overtime) score += 1
  if ((answer.attempts_count || 0) > 1) score += 1
  if ((answer.user_answer || '').trim().length < 20) score += 1
  return score
}

export type AiInsightsData = {
  test1Section?: TestSection | null
  aiSummary?: AISummary | null
}

function buildAiHints(sectionId: string, data: AiInsightsData): ScriptBlock[] {
  const hints: ScriptBlock[] = []
  const { test1Section, aiSummary } = data

  const test1Questions = (test1Section?.details?.questions || []) as TestQuestionAnswer[]
  const weakAnswers = test1Questions
    .slice()
    .sort((a, b) => questionWeight(b) - questionWeight(a))
    .filter((a) => questionWeight(a) >= 2)

  const test1Score = test1Section?.details?.stats?.final_score
  const test1Status = test1Section?.status

  const strengths = aiSummary?.strengths || []
  const risks = aiSummary?.risks || []
  const scorecard = aiSummary?.scorecard

  switch (sectionId) {
    case 'opening': {
      if (test1Status === 'passed' && typeof test1Score === 'number') {
        hints.push({
          type: 'ai-hint',
          icon: test1Score >= 3.5 ? '✓' : '!',
          label: 'Тест 1',
          text: `Результат: ${test1Score.toFixed(1)}/5. ${
            test1Score >= 4 ? 'Сильный результат — кандидат хорошо подготовлен.'
            : test1Score >= 3 ? 'Средний результат — уточните слабые зоны в разговоре.'
            : 'Слабый результат — обратите внимание на понимание формата работы.'
          }`,
        })
      }
      if (weakAnswers.length > 0) {
        const topics = weakAnswers
          .slice(0, 3)
          .map((a) => shorten(a.question_text, 60))
          .filter(Boolean)
        if (topics.length > 0) {
          hints.push({
            type: 'ai-hint',
            icon: '⚡',
            label: 'Слабые зоны из теста',
            text: topics.join(' · '),
          })
        }
      }
      if (scorecard?.recommendation) {
        hints.push({
          type: 'ai-hint',
          icon: '🤖',
          label: 'AI-рекомендация',
          text: scorecard.recommendation,
        })
      }
      break
    }

    case 'motivation': {
      const motivationAnswer = test1Questions.find(
        (a) => (a.question_text || '').toLowerCase().includes('мотив')
          || (a.question_text || '').toLowerCase().includes('почему'),
      )
      if (motivationAnswer?.user_answer) {
        hints.push({
          type: 'ai-hint',
          icon: '📝',
          label: 'Ответ из теста',
          text: `«${shorten(motivationAnswer.user_answer, 150)}»`,
        })
      }

      const incomeAnswer = test1Questions.find(
        (a) => (a.question_text || '').toLowerCase().includes('доход')
          || (a.question_text || '').toLowerCase().includes('зарплат'),
      )
      if (incomeAnswer?.user_answer) {
        hints.push({
          type: 'ai-hint',
          icon: '💰',
          label: 'Ожидания по доходу',
          text: `«${shorten(incomeAnswer.user_answer, 150)}»`,
        })
      }
      break
    }

    case 'company': {
      const formatAnswer = test1Questions.find(
        (a) => (a.question_text || '').toLowerCase().includes('формат')
          || (a.question_text || '').toLowerCase().includes('выезд')
          || (a.question_text || '').toLowerCase().includes('разъезд'),
      )
      if (formatAnswer?.user_answer) {
        const isWeak = questionWeight(formatAnswer) >= 2
        hints.push({
          type: 'ai-hint',
          icon: isWeak ? '⚠' : '✓',
          label: 'Готовность к формату',
          text: `«${shorten(formatAnswer.user_answer, 150)}»${isWeak ? ' — уточните этот вопрос подробнее.' : ''}`,
        })
      }
      break
    }

    case 'resilience': {
      const riskItems = risks.filter((r) =>
        r.label?.toLowerCase().includes('отказ')
        || r.label?.toLowerCase().includes('стресс')
        || r.label?.toLowerCase().includes('устойчив'),
      )
      if (riskItems.length > 0) {
        hints.push({
          type: 'ai-hint',
          icon: '⚠',
          label: 'AI-риск',
          text: riskItems.map((r) => r.label).join('. '),
        })
      }

      const strengthItems = strengths.filter((s) =>
        s.label?.toLowerCase().includes('коммуник')
        || s.label?.toLowerCase().includes('общен')
        || s.label?.toLowerCase().includes('стресс'),
      )
      if (strengthItems.length > 0) {
        hints.push({
          type: 'ai-hint',
          icon: '✓',
          label: 'Сильная сторона',
          text: strengthItems.map((s) => s.label).join('. '),
        })
      }
      break
    }

    case 'money': {
      const incomeAnswer = test1Questions.find(
        (a) => (a.question_text || '').toLowerCase().includes('доход')
          || (a.question_text || '').toLowerCase().includes('зарплат'),
      )
      if (incomeAnswer?.user_answer) {
        hints.push({
          type: 'ai-hint',
          icon: '💰',
          label: 'Из теста',
          text: `Ожидания кандидата: «${shorten(incomeAnswer.user_answer, 150)}»`,
        })
      }
      break
    }

    case 'intro-day': {
      if (aiSummary?.fit) {
        const { level, score } = aiSummary.fit
        const levelLabel = level === 'high' ? 'высокая' : level === 'medium' ? 'средняя' : 'низкая'
        hints.push({
          type: 'ai-hint',
          icon: '🎯',
          label: 'Релевантность',
          text: `${typeof score === 'number' ? `${score}/100` : ''} (${levelLabel}). ${
            level === 'high' ? 'Уверенно приглашайте на ОД.'
            : level === 'medium' ? 'Можно пригласить, но уточните сомнения.'
            : 'Рассмотрите отказ или дополнительную проверку.'
          }`,
        })
      }
      break
    }
  }

  return hints
}

export function buildScriptSections(candidateName: string, aiData?: AiInsightsData | null): ScriptSection[] {
  const name = candidateName || '{Имя}'

  const baseSections: ScriptSection[] = [
    {
      id: 'opening',
      step: 1,
      title: 'Вступительное слово',
      blocks: [
        { type: 'speech', text: `Здравствуйте, ${name}! Рад познакомиться. Как меня слышно, видно?` },
        { type: 'speech', text: 'Отлично. Я задам пару вопросов, коротко расскажу про формат и задачи. Цель простая — если мы понимаем, что вы подходите нам как кандидат и вам подходят условия вакансии, тогда я предложу вам ознакомительный день в офисе.' },
        { type: 'note', text: 'ОД — это 1.5–2 часа демо-версии работы с наставником. Завершающий этап перед обучением (1 неделя).' },
        { type: 'divider' },
        { type: 'prompt', text: 'Вы успели посмотреть вакансию перед откликом или отклик был массовый?' },
        {
          type: 'branch',
          condition: 'Ответ кандидата',
          options: [
            { label: 'Смотрел(а)', text: 'Что именно заинтересовало?' },
            { label: 'Нет / частично', text: 'Какие 2–3 критерия для вас самые важные при выборе работы? (график, доход, развитие, стабильность, коллектив)' },
          ],
        },
        { type: 'divider' },
        { type: 'speech', text: 'У нас работа активная. Примерно 70% времени — живые встречи с предпринимателями, 30% — офис: обучение, планёрки, документы. График 5/2, с 9:00 до 18:00.' },
        { type: 'prompt', text: 'Вам будет комфортно много общаться и быть в движении в течение дня?' },
        { type: 'prompt', text: 'Сколько времени вам добираться до офиса?' },
        { type: 'prompt', text: 'Был опыт общения с клиентами/людьми вживую?' },
        { type: 'note', text: 'Если есть сомнения: «Просто важно, чтобы формат вам подходил — тогда и результаты будут, и в работе будет комфортно».' },
      ],
    },
    {
      id: 'motivation',
      step: 2,
      title: 'Мотивация и доход',
      blocks: [
        { type: 'prompt', text: 'Почему вы сейчас в поиске работы?' },
        { type: 'prompt', text: 'Какую цель по доходу ставите себе на ближайшие 1–2 месяца?' },
        { type: 'prompt', text: 'Вам ближе стабильная фиксированная часть или возможность увеличивать доход за счёт личной активности?' },
        { type: 'note', text: 'Связка: «Понял, спасибо. Тогда буквально в двух словах, чем мы занимаемся и что делает менеджер.»' },
      ],
    },
    {
      id: 'company',
      step: 3,
      title: 'О компании и продуктах',
      blocks: [
        { type: 'speech', text: 'Мы помогаем бизнесу получать больше обращений через Яндекс.Карты. Частая ситуация: карточка оформлена слабо, информация устарела, фото некачественные — клиенты просто проходят мимо.' },
        { type: 'speech', text: 'Наша компания делает так, чтобы исключить подобные проблемы у бизнеса в сети. Что мы делаем:' },
        { type: 'note', text: '• Профессиональная съёмка: интерьерная или 3D-панорама\n• Обновление карточки: адрес, режим, контакты, описание, визуал\n• Техническая оптимизация профиля для поиска и просмотров' },
        { type: 'speech', text: 'В итоге карточка выглядит аккуратно, люди находят бизнес на картах, владелец видит прирост обращений. Мы этим занимаемся больше 7 лет. В компании сформированы внутренние отделы: технических специалистов, контент-менеджеров, сертифицированных фотографов.' },
        { type: 'divider' },
        { type: 'speech', text: 'Роль менеджера — первичная коммуникация. Вы общаетесь с предпринимателями, показываете, как можно улучшить профиль на картах. Это коммерческая работа, но «в лоб» никто не продаёт — важно уметь общаться и объяснять пользу.' },
        { type: 'prompt', text: 'Насколько вам интересно направление, где основа работы — общение и переговоры с владельцами бизнеса? Оцените интерес по шкале от 1 до 10.' },
      ],
    },
    {
      id: 'resilience',
      step: 4,
      title: 'Устойчивость к отказам',
      duration: '30–40 сек',
      blocks: [
        { type: 'speech', text: 'Отказы бывают — это нормально.' },
        { type: 'prompt', text: 'Когда вам говорят «неинтересно» или «нет времени» — вы обычно спокойно продолжаете или это сильно выбивает?' },
        { type: 'note', text: 'Коротко поддержать позицию. «В этой работе важны спокойствие и умение держать темп.»' },
      ],
    },
    {
      id: 'onboarding',
      step: 5,
      title: 'Обучение и вход в работу',
      duration: '30–40 сек',
      blocks: [
        { type: 'speech', text: 'Опыт в продажах не обязателен. Есть обучение и наставник: первые дни всё показывают на практике, разбирают ситуации, помогают выстроить переговоры. Обычно адаптация занимает 3–5 дней в зависимости от темпа.' },
      ],
    },
    {
      id: 'money',
      step: 6,
      title: 'Деньги',
      duration: '40–60 сек',
      blocks: [
        { type: 'speech', text: 'По доходу: на старте есть фиксированная часть + мотивация, дальше доход растёт от результатов.' },
        { type: 'speech', text: 'Для сильных кандидатов возможен формат с более высокой переменной частью. Система прозрачная: результат фиксируется, выплаты понятные.' },
        { type: 'note', text: 'Без «лекции» — коротко и по делу.' },
      ],
    },
    {
      id: 'intro-day',
      step: 7,
      title: 'Ознакомительный день',
      duration: '2–3 мин',
      blocks: [
        { type: 'speech', text: `Чтобы вы, ${name}, приняли решение не «в теории», предлагаю ознакомительный день. Это 1.5–2 часа в офисе с наставником: познакомитесь с процессом, посмотрим, как всё устроено, ответим на вопросы. После этого обычно становится понятно — подходит или нет.` },
        { type: 'prompt', text: 'По времени на завтра есть два варианта: 10:30 или 12:30. Как вам удобнее?' },
        { type: 'prompt', text: 'Как планируете добираться: метро или машина?' },
        { type: 'prompt', text: 'Во сколько вам нужно выехать, чтобы спокойно успеть?' },
        { type: 'divider' },
        { type: 'note', text: 'Важные правила (деловым тоном):' },
        { type: 'speech', text: 'Просьба прийти вовремя — наставник ждёт по расписанию. Дресс-код: аккуратный, деловой / смарт-кэжуал. Если что-то меняется — предупредите заранее, перенесём без проблем.' },
        { type: 'divider' },
        { type: 'speech', text: `Я сейчас закреплю за вами время. Небольшая просьба: напишите одним сообщением: «Подтверждаю, буду завтра в {время}».` },
      ],
    },
  ]

  if (!aiData) return baseSections

  return baseSections.map((section) => {
    const aiHints = buildAiHints(section.id, aiData)
    if (aiHints.length === 0) return section
    return {
      ...section,
      blocks: [...aiHints, { type: 'divider' as const }, ...section.blocks],
    }
  })
}
