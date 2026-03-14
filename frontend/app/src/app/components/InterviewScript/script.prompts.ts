import type { InterviewScriptPayload, TestQuestionAnswer } from '@/api/services/candidates'

import type { InterviewScriptBaseContext, InterviewScriptQuestionView, InterviewScriptViewModel } from './script.types'

const STANDARD_QUESTIONS: InterviewScriptQuestionView[] = [
  {
    id: 'standard-motivation',
    text: 'Почему вам сейчас интересна именно эта вакансия и что для вас будет главным критерием выбора работы?',
    type: 'standard',
    source: null,
    why: 'Понимаем реальную мотивацию кандидата и не ведём дальше человека с поверхностным интересом.',
    goodAnswer: 'Говорит предметно, понимает, зачем идёт на позицию, и связывает мотивацию с реальной ролью.',
    redFlags: 'Отвечает слишком общо, не понимает вакансию или ищет просто «любую работу».',
    estimatedMinutes: 3,
  },
  {
    id: 'standard-conditions',
    text: 'Какие условия для вас критичны: доход, график, локация, формат работы или обучение?',
    type: 'standard',
    source: null,
    why: 'Снимаем риск расхождения ожиданий до следующего этапа.',
    goodAnswer: 'Расставляет приоритеты и объясняет, где возможен компромисс, а где нет.',
    redFlags: 'Не может назвать критерии или озвучивает взаимоисключающие ожидания.',
    estimatedMinutes: 2,
  },
  {
    id: 'standard-availability',
    text: 'Когда вы готовы выйти на следующий этап и есть ли сейчас другие активные предложения?',
    type: 'standard',
    source: null,
    why: 'Понимаем срочность кандидата и риск потери на следующих шагах.',
    goodAnswer: 'Называет конкретные сроки и открыто говорит о других процессах.',
    redFlags: 'Избегает конкретики по срокам или скрывает важные ограничения по времени.',
    estimatedMinutes: 2,
  },
]

const DEFAULT_CLOSING_CHECKLIST = [
  'Ожидания по доходу и формату работы',
  'Готовность к следующему этапу и возможная дата выхода',
  'Другие активные предложения или ограничения по времени',
]

function shorten(value: string | null | undefined, limit = 120) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.length <= limit) return text
  return `${text.slice(0, Math.max(0, limit - 1)).trim()}…`
}

function firstName(value: string) {
  const [name] = value.trim().split(/\s+/).filter(Boolean)
  return name || 'кандидат'
}

function questionWeight(answer: TestQuestionAnswer) {
  let score = 0
  if (answer.is_correct === false) score += 3
  if (answer.overtime) score += 1
  if ((answer.attempts_count || 0) > 1) score += 1
  if ((answer.user_answer || '').trim().length < 20) score += 1
  return score
}

function personalizedQuestion(answer: TestQuestionAnswer, index: number): InterviewScriptQuestionView | null {
  const questionText = String(answer.question_text || '').trim()
  if (!questionText) return null
  const questionLc = questionText.toLowerCase()
  const shortAnswer = shorten(answer.user_answer, 90)
  let text = `В тесте был вопрос «${questionText}». Расскажите подробнее, как вы бы действовали в похожей рабочей ситуации.`
  let why = 'Проверяем реальный опыт и глубину ответа в зоне, где тест дал слабый или неполный сигнал.'
  let goodAnswer = 'Даёт конкретику, приводит пример из опыта, описывает свои действия и делает вывод.'
  let redFlags = 'Уходит от ответа, говорит общими словами или не может привести реальный пример.'

  if (questionLc.includes('формат') || questionLc.includes('выезд') || questionLc.includes('разъезд')) {
    text = 'Насколько вам действительно подходит выездной и полевой формат работы в течение дня? Опишите, что для вас в нём комфортно, а что нет.'
    why = 'Проверяем, совпадает ли реальная готовность кандидата с форматом работы, который потребуется на позиции.'
    goodAnswer = 'Спокойно подтверждает формат, говорит о бытовой готовности и даёт пример похожего режима.'
    redFlags = 'Хочет только офисный формат или явно не готов к активному ритму дня.'
  } else if (questionLc.includes('доход') || questionLc.includes('зарплат')) {
    text = 'Какой уровень дохода для вас реалистичен на старте и что должно произойти, чтобы вы считали предложение сильным?'
    why = 'Снимаем риск по ожиданиям к доходу до следующего этапа.'
    goodAnswer = 'Называет реалистичный диапазон и связывает его с объёмом работы.'
    redFlags = 'Озвучивает завышенные ожидания без логики или уходит от конкретики.'
  } else if (questionLc.includes('мотив')) {
    text = `В тесте вы коротко описали мотивацию: «${shortAnswer}». Что для вас будет показателем удачного первого месяца на новой работе?`
  } else if (shortAnswer) {
    text = `В тесте вы ответили: «${shortAnswer}». Расскажите подробнее, как это проявлялось в реальной работе.`
  }

  return {
    id: `personalized-${answer.question_index || index}`,
    text,
    type: 'personalized',
    source: answer.question_index ? `test1_q_${answer.question_index}` : null,
    why,
    goodAnswer,
    redFlags,
    estimatedMinutes: 3,
  }
}

export function buildInterviewScriptViewModel(
  payload: InterviewScriptPayload,
  context: InterviewScriptBaseContext,
): InterviewScriptViewModel {
  const first = firstName(context.candidateName)
  const payloadQuestions = (payload.questions || []).map((question) => ({
    id: question.id,
    text: question.text,
    type: question.type,
    source: question.source,
    why: question.why,
    goodAnswer: question.good_answer,
    redFlags: question.red_flags,
    estimatedMinutes: question.estimated_minutes,
  }))

  const fallbackQuestions = ((context.test1Section?.details?.questions || []) as TestQuestionAnswer[])
    .slice()
    .sort((left, right) => questionWeight(right) - questionWeight(left))
    .map((answer, index) => personalizedQuestion(answer, index + 1))
    .filter((item): item is InterviewScriptQuestionView => Boolean(item))

  const mergedQuestions = payloadQuestions.length > 0 ? payloadQuestions : fallbackQuestions
  const questions = [...mergedQuestions]
  for (const question of STANDARD_QUESTIONS) {
    if (questions.length >= 7) break
    if (!questions.some((item) => item.id === question.id)) {
      questions.push(question)
    }
  }

  const briefingFocusAreas = payload.briefing?.focus_areas?.filter(Boolean) || fallbackQuestions.slice(0, 3).map((item) => item.why)
  const briefingFlags = payload.briefing?.key_flags?.filter(Boolean) || payload.checks?.slice(0, 3) || []

  return {
    title: payload.stage_label || 'Интервью с кандидатом',
    goal:
      payload.briefing?.goal ||
      payload.call_goal ||
      `Понять реальную релевантность ${first} и принять решение по следующему шагу.`,
    briefingFocusAreas,
    briefingFlags,
    greeting:
      payload.opening?.greeting ||
      `${first}, здравствуйте. Спасибо, что нашли время. Я коротко уточню опыт, ожидания и формат работы, а затем зафиксирую следующий шаг.`,
    icebreakers:
      payload.opening?.icebreakers?.filter(Boolean) || [
        'Как вам удобнее: сначала коротко рассказать про вакансию или сначала сверить ваши ожидания?',
        'Какой результат этого разговора будет для вас полезным?',
        'Вы сейчас активно выбираете работу или только присматриваетесь?',
      ],
    questions: questions.slice(0, 8),
    closingChecklist: payload.closing_checklist?.filter(Boolean) || DEFAULT_CLOSING_CHECKLIST,
    closingPhrase:
      payload.closing_phrase ||
      'Спасибо за ответы. Я зафиксирую всё в системе, сверю следующий шаг и обязательно вернусь к вам с точным решением и деталями.',
    rawScript: payload,
  }
}

export const INTERVIEW_RECOMMENDATION_LABELS: Record<'recommend' | 'doubt' | 'not_recommend', string> = {
  recommend: 'Рекомендую',
  doubt: 'Сомневаюсь',
  not_recommend: 'Не рекомендую',
}
