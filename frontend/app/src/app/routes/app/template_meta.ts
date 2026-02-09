/**
 * Human-readable metadata for every known notification template key.
 *
 * stage  – recruitment stage the message belongs to
 * title  – short Russian title shown in the UI
 * desc   – one-liner explaining *when* the message is sent
 */

export type TemplateStage =
  | 'registration'
  | 'testing'
  | 'interview'
  | 'intro_day'
  | 'reminders'
  | 'results'
  | 'service'

export type TemplateMeta = {
  title: string
  stage: TemplateStage
  desc: string
}

export const STAGE_LABELS: Record<TemplateStage, { title: string; desc: string }> = {
  registration: {
    title: 'Регистрация',
    desc: 'Первичные сообщения: выбор рекрутёра, резервирование, ручная запись.',
  },
  testing: {
    title: 'Тестирование',
    desc: 'Отправка тестов, прогресс, результаты, форматные отказы.',
  },
  interview: {
    title: 'Собеседование',
    desc: 'Приглашения на интервью, подтверждения слотов, перезапись.',
  },
  intro_day: {
    title: 'Ознакомительный день',
    desc: 'Приглашения на ознакомительный день, адреса и инструкции.',
  },
  reminders: {
    title: 'Напоминания и подтверждения',
    desc: 'Напоминания за N часов, подтверждения явки.',
  },
  results: {
    title: 'Результаты и решения',
    desc: 'Оффер, отказ, итоги собеседования.',
  },
  service: {
    title: 'Служебные',
    desc: 'Уведомления рекрутёрам, сервисные и прочие сообщения.',
  },
}

export const TEMPLATE_META: Record<string, TemplateMeta> = {
  // ── Registration ──────────────────────────────────────────────
  choose_recruiter: {
    title: 'Выбор рекрутёра',
    stage: 'registration',
    desc: 'Кандидату предлагают выбрать рекрутёра для записи.',
  },
  existing_reservation: {
    title: 'Существующая бронь',
    stage: 'registration',
    desc: 'Кандидат пытается записаться повторно — показывается текущая бронь.',
  },
  manual_schedule_prompt: {
    title: 'Ручная запись',
    stage: 'registration',
    desc: 'Рекрутёру недоступны слоты — предложение записать вручную.',
  },
  no_slots: {
    title: 'Нет свободных слотов',
    stage: 'registration',
    desc: 'Нет доступных слотов для записи кандидата.',
  },

  // ── Testing ───────────────────────────────────────────────────
  t1_intro: {
    title: 'Тест 1 — вступление',
    stage: 'testing',
    desc: 'Первое сообщение перед началом Теста 1.',
  },
  t1_progress: {
    title: 'Тест 1 — прогресс',
    stage: 'testing',
    desc: 'Промежуточное сообщение о прохождении Теста 1.',
  },
  t1_done: {
    title: 'Тест 1 — завершён',
    stage: 'testing',
    desc: 'Тест 1 завершён, кандидат получает результат.',
  },
  t1_format_reject: {
    title: 'Тест 1 — отказ (формат)',
    stage: 'testing',
    desc: 'Ответ кандидата не прошёл проверку формата.',
  },
  t1_format_clarify: {
    title: 'Тест 1 — уточнение формата',
    stage: 'testing',
    desc: 'Кандидату предлагают исправить формат ответа.',
  },
  t1_schedule_reject: {
    title: 'Тест 1 — отказ в записи',
    stage: 'testing',
    desc: 'Кандидат не прошёл Тест 1 и не может записаться.',
  },
  t2_intro: {
    title: 'Тест 2 — вступление',
    stage: 'testing',
    desc: 'Первое сообщение перед началом Теста 2.',
  },
  t2_result: {
    title: 'Тест 2 — результат',
    stage: 'testing',
    desc: 'Результат прохождения Теста 2.',
  },

  // ── Interview ─────────────────────────────────────────────────
  slot_taken: {
    title: 'Слот занят',
    stage: 'interview',
    desc: 'Выбранный слот уже занят другим кандидатом.',
  },
  slot_sent: {
    title: 'Слот отправлен',
    stage: 'interview',
    desc: 'Кандидату отправлены детали забронированного слота.',
  },
  slot_reschedule: {
    title: 'Перезапись слота',
    stage: 'interview',
    desc: 'Кандидат запросил перенос собеседования.',
  },
  slot_proposal_candidate: {
    title: 'Предложение слота кандидату',
    stage: 'interview',
    desc: 'Кандидату предлагают конкретный слот на выбор.',
  },
  slot_proposal: {
    title: 'Предложение слота',
    stage: 'interview',
    desc: 'Предложение слота (общее).',
  },
  interview_confirmed_candidate: {
    title: 'Подтверждение записи (кандидат)',
    stage: 'interview',
    desc: 'Кандидат получает подтверждение записи на собеседование.',
  },
  interview_confirmed: {
    title: 'Интервью подтверждено',
    stage: 'interview',
    desc: 'Подтверждение, что собеседование состоится.',
  },
  interview_preparation: {
    title: 'Подготовка к интервью',
    stage: 'interview',
    desc: 'Инструкции для кандидата перед собеседованием.',
  },
  interview_invite_details: {
    title: 'Приглашение — детали',
    stage: 'interview',
    desc: 'Детальное приглашение на собеседование с адресом и временем.',
  },
  candidate_reschedule_prompt: {
    title: 'Предложение перезаписи',
    stage: 'interview',
    desc: 'Кандидату предлагают перезаписаться на другое время.',
  },
  reschedule_prompt: {
    title: 'Запрос перезаписи',
    stage: 'interview',
    desc: 'Сообщение о возможности перезаписаться.',
  },
  reschedule_approved_candidate: {
    title: 'Перезапись одобрена',
    stage: 'interview',
    desc: 'Кандидату сообщают, что перенос одобрен.',
  },
  reschedule_declined_candidate: {
    title: 'Перезапись отклонена',
    stage: 'interview',
    desc: 'Кандидату сообщают, что перенос невозможен.',
  },
  slot_assignment_offer: {
    title: 'Назначение слота — предложение',
    stage: 'interview',
    desc: 'Рекрутёр предлагает кандидату конкретный слот.',
  },
  slot_assignment_reschedule_approved: {
    title: 'Назначение слота — перенос одобрен',
    stage: 'interview',
    desc: 'Перенос назначенного слота одобрен.',
  },
  slot_assignment_reschedule_declined: {
    title: 'Назначение слота — перенос отклонён',
    stage: 'interview',
    desc: 'Перенос назначенного слота отклонён.',
  },
  slot_assignment_reschedule_requested: {
    title: 'Назначение слота — запрос переноса',
    stage: 'interview',
    desc: 'Запрошен перенос назначенного слота.',
  },
  stage1_invite: {
    title: 'Этап 1 — приглашение',
    stage: 'interview',
    desc: 'Городской шаблон: приглашение на первый этап.',
  },

  // ── Intro Day ─────────────────────────────────────────────────
  intro_day_invitation: {
    title: 'Приглашение на ознакомительный день',
    stage: 'intro_day',
    desc: 'Кандидату отправляют приглашение на ознакомительный день с адресом.',
  },
  intro_day_invite_city: {
    title: 'Приглашение на озн. день (город)',
    stage: 'intro_day',
    desc: 'Городская версия приглашения на ознакомительный день.',
  },
  intro_day_reminder: {
    title: 'Напоминание об озн. дне',
    stage: 'intro_day',
    desc: 'Напоминание перед ознакомительным днём.',
  },
  intro_day_remind_2h: {
    title: 'Напоминание об озн. дне (2 ч)',
    stage: 'intro_day',
    desc: 'Напоминание за 2 часа до ознакомительного дня.',
  },
  stage3_intro_invite: {
    title: 'Этап 3 — приглашение на озн. день',
    stage: 'intro_day',
    desc: 'Городской шаблон: приглашение на ознакомительный день.',
  },
  stage4_intro_reminder: {
    title: 'Этап 4 — подтверждение озн. дня',
    stage: 'intro_day',
    desc: 'Городской шаблон: подтверждение перед ознакомительным днём.',
  },

  // ── Reminders & Confirmations ─────────────────────────────────
  reminder_2h: {
    title: 'Напоминание за 2 часа',
    stage: 'reminders',
    desc: 'Напоминание за 2 часа до интервью.',
  },
  reminder_30m: {
    title: 'Напоминание за 30 минут',
    stage: 'reminders',
    desc: 'Напоминание за 30 минут до интервью.',
  },
  reminder_3h: {
    title: 'Напоминание за 3 часа',
    stage: 'reminders',
    desc: 'Напоминание за 3 часа до интервью.',
  },
  reminder_6h: {
    title: 'Напоминание за 6 часов',
    stage: 'reminders',
    desc: 'Напоминание за 6 часов до интервью.',
  },
  confirm_6h: {
    title: 'Подтверждение за 6 часов',
    stage: 'reminders',
    desc: 'Запрос подтверждения явки за 6 часов.',
  },
  confirm_2h: {
    title: 'Подтверждение за 2 часа',
    stage: 'reminders',
    desc: 'Запрос подтверждения явки за 2 часа.',
  },
  att_confirmed_link: {
    title: 'Явка подтверждена — ссылка',
    stage: 'reminders',
    desc: 'Кандидат подтвердил явку; отправляется ссылка на встречу.',
  },
  att_confirmed_ack: {
    title: 'Явка подтверждена — ack',
    stage: 'reminders',
    desc: 'Подтверждение принято, спасибо.',
  },
  att_declined: {
    title: 'Явка отклонена',
    stage: 'reminders',
    desc: 'Кандидат отказался от встречи.',
  },
  stage2_interview_reminder: {
    title: 'Этап 2 — напоминание',
    stage: 'reminders',
    desc: 'Городской шаблон: напоминание за 2 ч до интервью.',
  },
  interview_remind_confirm_2h: {
    title: 'Напоминание + подтверждение (2 ч)',
    stage: 'reminders',
    desc: 'Напоминание за 2 часа с просьбой подтвердить явку.',
  },
  no_show_gentle: {
    title: 'Неявка (мягкое)',
    stage: 'reminders',
    desc: 'Мягкое уведомление кандидату о пропуске встречи.',
  },

  // ── Results & Decisions ───────────────────────────────────────
  approved_msg: {
    title: 'Кандидат одобрен',
    stage: 'results',
    desc: 'Кандидат успешно прошёл этап — положительное решение.',
  },
  result_fail: {
    title: 'Отказ по результатам',
    stage: 'results',
    desc: 'Кандидат не прошёл собеседование.',
  },
  candidate_rejection: {
    title: 'Отказ кандидату',
    stage: 'results',
    desc: 'Общее уведомление об отказе.',
  },

  // ── Service / Recruiter-facing ────────────────────────────────
  slot_confirmed_recruiter: {
    title: 'Слот подтверждён (рекрутёр)',
    stage: 'service',
    desc: 'Рекрутёру: кандидат подтвердил слот.',
  },
  reschedule_requested_recruiter: {
    title: 'Запрос переноса (рекрутёр)',
    stage: 'service',
    desc: 'Рекрутёру: кандидат запросил перенос.',
  },
  recruiter_candidate_confirmed_notice: {
    title: 'Уведомление рекрутёру о подтверждении',
    stage: 'service',
    desc: 'Рекрутёру: кандидат подтвердил запись.',
  },
}

/** Look up title for a key; fall back to the raw key. */
export function templateTitle(key: string): string {
  return TEMPLATE_META[key]?.title ?? key
}

/** Look up stage for a key; fall back to 'service'. */
export function templateStage(key: string): TemplateStage {
  return TEMPLATE_META[key]?.stage ?? 'service'
}

/** Look up description for a key. */
export function templateDesc(key: string): string {
  return TEMPLATE_META[key]?.desc ?? ''
}
