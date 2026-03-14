import { formatRescheduleRequest } from '@/shared/utils/labels'

import { CONFIRMED_SLOT_STATUSES, URL_RE } from './messenger.constants'
import type {
  AISummary,
  CandidateChatMessage,
  CandidateChatThread,
  CandidateChatThreadsPayload,
  CandidateChatWorkspaceState,
  CandidateDetail,
  GroupedMessageRow,
  IntroDayTemplateContext,
  JourneyStep,
  NextAction,
  ThreadTone,
} from './messenger.types'

export function priorityTone(bucket?: CandidateChatThread['priority_bucket'] | null): ThreadTone {
  switch (bucket) {
    case 'overdue':
      return 'danger'
    case 'needs_reply':
    case 'blocked':
    case 'follow_up':
      return 'warning'
    case 'waiting_candidate':
      return 'info'
    case 'system':
      return 'neutral'
    case 'terminal':
      return 'danger'
    default:
      return 'success'
  }
}

export function priorityLabel(bucket?: CandidateChatThread['priority_bucket'] | null): string {
  switch (bucket) {
    case 'overdue':
      return 'Просрочен ответ'
    case 'needs_reply':
      return 'Нужен ответ'
    case 'blocked':
      return 'Подтверждение / блокер'
    case 'waiting_candidate':
      return 'Ждём кандидата'
    case 'follow_up':
      return 'Нужен follow-up'
    case 'system':
      return 'Системный'
    case 'terminal':
      return 'Закрытый статус'
    default:
      return 'В работе'
  }
}

export function formatThreadTime(value?: string | null): string {
  if (!value) return ''
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return ''
  const today = new Date()
  if (dt.toDateString() === today.toDateString()) {
    return dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }
  return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

export function formatFullDateTime(value?: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDayLabel(value: string): string {
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return 'Сегодня'
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (dt.toDateString() === today.toDateString()) return 'Сегодня'
  if (dt.toDateString() === yesterday.toDateString()) return 'Вчера'
  return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long' })
}

export function previewText(thread?: CandidateChatThread | null): string {
  return thread?.last_message_preview?.trim() || thread?.last_message?.preview?.trim() || thread?.last_message?.text?.trim() || 'Переписка ещё не началась'
}

export function compactThreadStatusLabel(
  status?: string | null,
  bucket?: CandidateChatThread['priority_bucket'] | null,
): string {
  const normalized = (status || '').toLowerCase()
  if (!normalized) return priorityLabel(bucket)
  if (normalized.includes('отказ')) return 'Отказ'
  if (normalized.includes('собесед')) return 'Собеседование'
  if (normalized.includes('ознаком')) return 'Ознакомление'
  if (normalized.includes('подтверж')) return 'Подтверждён'
  if (normalized.includes('перенос')) return 'Перенос'
  if (normalized.includes('ожид')) return 'Ожидание'
  return status!.length > 24 ? `${status!.slice(0, 24).trim()}…` : status!
}

export function messageAuthorLabel(message: CandidateChatMessage): string {
  if (message.kind === 'candidate' || message.direction === 'inbound') return message.author || 'Кандидат'
  if (message.kind === 'bot') return 'Бот'
  if (message.kind === 'system') return 'Система'
  return message.author || 'Вы'
}

export function readThreadCache(
  payload: CandidateChatThreadsPayload | undefined,
  candidateId: number,
): CandidateChatThreadsPayload | undefined {
  if (!payload) return payload
  return {
    ...payload,
    threads: (payload.threads || []).map((thread) =>
      thread.candidate_id === candidateId ? { ...thread, unread_count: 0 } : thread,
    ),
  }
}

export function scoreTone(score?: number | null, level?: string | null): ThreadTone {
  if (typeof score === 'number') {
    if (score >= 80) return 'success'
    if (score >= 60) return 'info'
    if (score >= 40) return 'warning'
    return 'danger'
  }
  if (level === 'high') return 'success'
  if (level === 'medium') return 'info'
  if (level === 'low') return 'warning'
  return 'neutral'
}

export function normalizeTextLinks(text?: string | null): string[] {
  if (!text) return []
  const matches = text.match(URL_RE) || []
  return Array.from(new Set(matches))
}

export function splitMessageText(text?: string | null): string[] {
  return (text || '…').split(URL_RE)
}

export function upcomingSlot(detail?: CandidateDetail | null) {
  return (detail?.slots || [])
    .filter((slot) => Boolean(slot.start_utc))
    .map((slot) => ({
      ...slot,
      timestamp: new Date(slot.start_utc as string).getTime(),
    }))
    .filter((slot) => Number.isFinite(slot.timestamp) && slot.timestamp >= Date.now())
    .sort((left, right) => left.timestamp - right.timestamp)[0] || null
}

export function slotConfirmationLabel(slot?: NonNullable<CandidateDetail['slots']>[number] | null): string {
  if (!slot?.start_utc) return 'Следующий шаг ещё не подтверждён'
  const normalizedStatus = (slot.status || '').trim().toUpperCase()
  if (CONFIRMED_SLOT_STATUSES.has(normalizedStatus)) {
    return slot.purpose === 'intro_day' ? 'Ознакомительный день подтверждён' : 'Собеседование подтверждено'
  }
  return slot.purpose === 'intro_day' ? 'Ждём подтверждение ознакомительного дня' : 'Ждём подтверждение собеседования'
}

export function testSection(detail: CandidateDetail | null | undefined, key: 'test1' | 'test2') {
  return (detail?.test_sections || []).find((section) => section.key === key)
}

export function findPurposeSlot(detail: CandidateDetail | null | undefined, purpose: 'interview' | 'intro_day') {
  return (detail?.slots || [])
    .filter((slot) => (slot.purpose || 'interview') === purpose && slot.start_utc)
    .map((slot) => ({ ...slot, timestamp: new Date(slot.start_utc as string).getTime() }))
    .filter((slot) => Number.isFinite(slot.timestamp))
    .sort((left, right) => right.timestamp - left.timestamp)[0] || null
}

export function findUpcomingPurposeSlot(detail: CandidateDetail | null | undefined, purpose: 'interview' | 'intro_day') {
  return (detail?.slots || [])
    .filter((slot) => (slot.purpose || 'interview') === purpose && slot.start_utc)
    .map((slot) => ({ ...slot, timestamp: new Date(slot.start_utc as string).getTime() }))
    .filter((slot) => Number.isFinite(slot.timestamp) && slot.timestamp >= Date.now())
    .sort((left, right) => left.timestamp - right.timestamp)[0] || null
}

export function pipelineState(raw?: string | null): JourneyStep['state'] {
  if (raw === 'passed') return 'passed'
  if (raw === 'active') return 'active'
  if (raw === 'declined') return 'declined'
  return 'pending'
}

export function isFieldFormatQuestion(text?: string | null): boolean {
  const normalized = (text || '').toLowerCase()
  return Boolean(
    normalized &&
      (
        normalized.includes('полев') ||
        normalized.includes('разъезд') ||
        normalized.includes('выезд') ||
        normalized.includes('в движении') ||
        (normalized.includes('формат') && normalized.includes('работ'))
      )
  )
}

export function fieldFormatAnswer(detail?: CandidateDetail | null): string | null {
  const question = (testSection(detail, 'test1')?.details?.questions || []).find((item) => isFieldFormatQuestion(item.question_text))
  const answer = question?.user_answer?.trim()
  return answer || null
}

export function buildNextAction(
  thread: CandidateChatThread | null,
  detail?: CandidateDetail | null,
  aiSummary?: AISummary | null,
  workspace?: CandidateChatWorkspaceState | null,
): NextAction {
  if (!thread) {
    return {
      label: 'Выберите диалог',
      reason: 'Слева появится история переписки и рабочий контекст.',
      outcome: 'После выбора будет видно этап кандидата и следующее действие.',
      tone: 'neutral',
      ctaKind: 'none',
      ctaLabel: null,
    }
  }
  const reschedule = formatRescheduleRequest(detail?.reschedule_request)
  const interviewSlot = findUpcomingPurposeSlot(detail, 'interview') || findPurposeSlot(detail, 'interview')
  const introDaySlot = findUpcomingPurposeSlot(detail, 'intro_day') || findPurposeSlot(detail, 'intro_day')
  const t1 = testSection(detail, 'test1')
  const t2 = testSection(detail, 'test2')
  const recommendation = aiSummary?.scorecard?.recommendation

  if (detail?.status_is_terminal) {
    return {
      label: detail.workflow_status_label || detail.candidate_status_display || 'Процесс завершён',
      reason: 'Кандидат находится в завершённом статусе, активных шагов по воронке больше нет.',
      outcome: 'Можно только открыть карточку для ручной перепроверки или заархивировать чат.',
      tone: 'neutral',
      ctaKind: thread.is_archived ? 'archive' : (thread.profile_url ? 'profile' : 'none'),
      ctaLabel: thread.is_archived ? 'Вернуть из архива' : (thread.profile_url ? 'Открыть карточку' : null),
    }
  }

  if (reschedule) {
    return {
      label: 'Согласовать новый слот',
      reason: `Кандидат запросил перенос: ${reschedule.summary}.`,
      outcome: 'После нового слота кандидат вернётся в этап собеседования без потери контекста.',
      tone: 'warning',
      ctaKind: thread.profile_url ? 'profile' : 'none',
      ctaLabel: thread.profile_url ? 'Открыть карточку' : null,
    }
  }

  if (detail?.can_schedule_intro_day) {
    return {
      label: 'Записать на ознакомительный день',
      reason:
        t2?.status === 'passed'
          ? 'Кандидат прошёл проверку перед ОД и готов к следующему практическому этапу.'
          : 'По этапу воронки уже можно переводить кандидата на ознакомительный день.',
      outcome: 'После назначения останется подтвердить явку и довести кандидата до посещения офиса.',
      tone: recommendation === 'od_recommended' ? 'success' : 'info',
      ctaKind: 'intro_day',
      ctaLabel: introDaySlot ? 'Обновить ОД' : 'Назначить ОД',
    }
  }

  if (introDaySlot?.start_utc) {
    return {
      label: 'Подтвердить явку на ОД',
      reason: `${slotConfirmationLabel(introDaySlot)} · ${formatFullDateTime(introDaySlot.start_utc)}.`,
      outcome: 'После подтверждения кандидата остаётся дождаться ОД и зафиксировать итог.',
      tone: CONFIRMED_SLOT_STATUSES.has((introDaySlot.status || '').toUpperCase()) ? 'success' : 'warning',
      ctaKind: 'intro_day',
      ctaLabel: 'Открыть ОД',
    }
  }

  if (t1?.status === 'passed' && !interviewSlot) {
    return {
      label: 'Назначить собеседование',
      reason: 'Тест 1 пройден, но активного слота собеседования ещё нет.',
      outcome: 'После назначения нужно будет подтвердить явку и довести кандидата до интервью.',
      tone: 'info',
      ctaKind: thread.profile_url ? 'profile' : 'none',
      ctaLabel: thread.profile_url ? 'Открыть карточку' : null,
    }
  }

  if (interviewSlot?.start_utc) {
    const confirmed = CONFIRMED_SLOT_STATUSES.has((interviewSlot.status || '').toUpperCase())
    return {
      label: confirmed ? 'Держать кандидата в контакте до собеседования' : 'Подтвердить явку на собеседование',
      reason: `Собеседование ${confirmed ? 'подтверждено' : 'назначено'} на ${formatFullDateTime(interviewSlot.start_utc)}.`,
      outcome: confirmed
        ? 'После интервью можно будет принять решение по следующему этапу.'
        : 'После подтверждения кандидат перестанет висеть между слотом и фактическим интервью.',
      tone: confirmed ? 'success' : 'warning',
      ctaKind: thread.profile_url ? 'profile' : 'none',
      ctaLabel: thread.profile_url ? 'Открыть карточку' : null,
    }
  }

  if (recommendation === 'not_recommended') {
    return {
      label: 'Принять решение по кандидату',
      reason: 'AI и текущий этап указывают, что кандидата нужно либо закрывать, либо вручную перепроверять.',
      outcome: 'После решения воронка завершится без лишних касаний и ручных напоминаний.',
      tone: 'danger',
      ctaKind: thread.profile_url ? 'profile' : 'none',
      ctaLabel: thread.profile_url ? 'Открыть карточку' : null,
    }
  }

  if (thread.priority_bucket === 'overdue' || thread.priority_bucket === 'needs_reply') {
    return {
      label: 'Повторный контакт',
      reason: thread.unread_count ? `Кандидат ждёт ответ, новых сообщений: ${thread.unread_count}.` : 'Диалог требует ответа со стороны рекрутера.',
      outcome: 'Ответ в чате вернёт кандидата в рабочий ритм и не даст процессу зависнуть.',
      tone: thread.priority_bucket === 'overdue' ? 'danger' : 'warning',
      ctaKind: 'none',
      ctaLabel: null,
    }
  }

  if (workspace?.follow_up_due_at) {
    return {
      label: 'Повторно связаться',
      reason: `В workspace уже зафиксирован срок follow-up: ${formatFullDateTime(workspace.follow_up_due_at)}.`,
      outcome: 'После нового касания чат снова станет активным и SLA перестанет подсвечиваться.',
      tone: 'info',
      ctaKind: 'none',
      ctaLabel: null,
    }
  }

  return {
    label: 'Поддерживать контакт',
    reason: 'Критичных блокеров сейчас нет, но чат остаётся рабочим каналом до следующего этапа.',
    outcome: 'Если кандидат задаст вопрос или пропадёт, это сразу будет видно по приоритету треда.',
    tone: priorityTone(thread.priority_bucket),
    ctaKind: thread.profile_url ? 'profile' : 'none',
    ctaLabel: thread.profile_url ? 'Открыть карточку' : null,
  }
}

export function buildJourneySteps(
  thread: CandidateChatThread,
  detail?: CandidateDetail | null,
): JourneyStep[] {
  const stages = detail?.pipeline_stages || [
    { key: 'lead', label: 'Лид', state: 'active' },
    { key: 'test', label: 'Тест', state: 'pending' },
    { key: 'interview', label: 'Собеседование', state: 'pending' },
    { key: 'intro_day', label: 'Ознакомительный день', state: 'pending' },
    { key: 'outcome', label: 'Итог', state: 'pending' },
  ]
  const interviewSlot = findUpcomingPurposeSlot(detail, 'interview') || findPurposeSlot(detail, 'interview')
  const introDaySlot = findUpcomingPurposeSlot(detail, 'intro_day') || findPurposeSlot(detail, 'intro_day')
  const recruiter =
    interviewSlot?.recruiter_name || introDaySlot?.recruiter_name || detail?.responsible_recruiter?.name || 'Рекрутер'
  const reschedule = formatRescheduleRequest(detail?.reschedule_request)
  const t1 = testSection(detail, 'test1')
  const t2 = testSection(detail, 'test2')

  return stages.map((stage) => {
    const state = pipelineState(stage.state)
    if (stage.key === 'lead') {
      return {
        key: stage.key,
        label: stage.label,
        state,
        headline:
          t1?.status === 'passed'
            ? 'Лид уже прошёл тест и готов к следующему шагу.'
            : `Кандидат добавлен в CRM${thread.created_at ? ` · ${formatFullDateTime(thread.created_at)}` : ''}.`,
        detailLines: [
          `Город: ${detail?.city || thread.city || 'не указан'}`,
          `Текущий workflow: ${detail?.workflow_status_label || thread.status_label || 'в работе'}`,
        ],
        nextHint: 'Дальше кандидат должен пройти тест и первичную проверку.',
      }
    }
    if (stage.key === 'test') {
      const lines = [
        `Тест 1: ${t1?.summary || 'ещё не проходил'}`,
        t1?.completed_at ? `Дата: ${formatFullDateTime(t1.completed_at)}` : 'Дата: ещё не завершён',
      ]
      if (t2) {
        lines.push(`Тест 2: ${t2.summary || t2.status_label || t2.status || 'нет данных'}`)
      }
      return {
        key: stage.key,
        label: stage.label,
        state,
        headline:
          t1?.status === 'passed'
            ? 'Тестовый этап закрыт, есть база для решения по интервью.'
            : t1?.status === 'in_progress'
              ? 'Тестовый этап ещё в работе.'
              : 'Тестовый этап требует проверки.',
        detailLines: lines,
        nextHint: interviewSlot ? 'Дальше нужно довести кандидата до собеседования.' : 'Если ответы ок, следующим шагом назначается собеседование.',
      }
    }
    if (stage.key === 'interview') {
      const lines = interviewSlot?.start_utc
        ? [
            `Слот: ${formatFullDateTime(interviewSlot.start_utc)}`,
            `Статус слота: ${slotConfirmationLabel(interviewSlot)}`,
            `Кто ведёт: ${recruiter}`,
            ...(reschedule?.comment ? [`Комментарий кандидата: ${reschedule.comment}`] : []),
          ]
        : ['Слот интервью пока не закреплён.', `Кто ведёт: ${recruiter}`]
      return {
        key: stage.key,
        label: stage.label,
        state: reschedule ? 'declined' : state,
        headline: reschedule
          ? `Есть проблема по этапу: ${reschedule.summary}.`
          : interviewSlot?.start_utc
            ? 'Собеседование уже заведено в воронку.'
            : 'Этап собеседования ещё не запущен.',
        detailLines: lines,
        nextHint: reschedule ? 'Нужно согласовать новый слот и вернуть кандидата к нормальному ритму.' : 'После собеседования решение уходит либо в ОД, либо в итог.',
      }
    }
    if (stage.key === 'intro_day') {
      const lines = introDaySlot?.start_utc
        ? [
            `ОД: ${formatFullDateTime(introDaySlot.start_utc)}`,
            `Статус: ${slotConfirmationLabel(introDaySlot)}`,
            `Кто ведёт: ${recruiter}`,
          ]
        : [
            detail?.can_schedule_intro_day ? 'Этап уже открыт, можно назначать ознакомительный день.' : 'Ознакомительный день пока не назначен.',
            `Кто ведёт: ${recruiter}`,
          ]
      return {
        key: stage.key,
        label: stage.label,
        state,
        headline:
          introDaySlot?.start_utc
            ? 'Ознакомительный день уже стоит в воронке.'
            : detail?.can_schedule_intro_day
              ? 'Кандидат готов к назначению ознакомительного дня.'
              : 'Этап ознакомительного дня ещё не активен.',
        detailLines: lines,
        nextHint: 'После ОД остаётся зафиксировать итог и закрыть решение по кандидату.',
      }
    }
    return {
      key: stage.key,
      label: stage.label,
      state,
      headline:
        detail?.status_is_terminal
          ? `${detail.workflow_status_label || detail.candidate_status_display || 'Итог зафиксирован'}.`
          : 'Финальное решение ещё не зафиксировано.',
      detailLines: [
        `Текущий статус: ${detail?.workflow_status_label || thread.status_label || 'в работе'}`,
        `Риск: ${thread.risk_hint || 'критичных рисков не зафиксировано'}`,
      ],
      nextHint: detail?.status_is_terminal ? 'Новых действий по воронке не требуется.' : 'Финальный статус появится после решения по кандидату.',
    }
  })
}

export function introDayFirstName(fio: string): string {
  const parts = fio.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return parts[1]
  return parts[0] || 'Кандидат'
}

export function formatIntroDayDate(dateStr: string): string {
  try {
    const [year, month, day] = dateStr.split('-')
    if (year && month && day) return `${day}.${month}`
  } catch {}
  return dateStr
}

export function renderIntroDayTemplate(
  template: string,
  candidateFio: string,
  dateStr: string,
  timeStr: string,
  templateContext?: IntroDayTemplateContext | null,
) {
  if (!template) return ''
  const firstName = introDayFirstName(candidateFio)
  const formattedDate = formatIntroDayDate(dateStr)
  const slotDateTime = [formattedDate, timeStr].filter(Boolean).join(' ').trim()
  const context: Record<string, string> = {
    candidate_name: candidateFio || firstName,
    candidate_fio: candidateFio || firstName,
    candidate_first_name: firstName,
    slot_date_local: formattedDate,
    slot_time_local: timeStr,
    slot_datetime_local: slotDateTime,
    dt_local: slotDateTime,
    interview_date_local: formattedDate,
    interview_time_local: timeStr,
    interview_datetime_local: slotDateTime,
    city_name: templateContext?.city_name || '',
    intro_address: templateContext?.intro_address || templateContext?.address || '',
    address: templateContext?.address || templateContext?.intro_address || '',
    city_address: templateContext?.city_address || templateContext?.intro_address || templateContext?.address || '',
    intro_contact: templateContext?.intro_contact || templateContext?.recruiter_contact || '',
    recruiter_contact: templateContext?.recruiter_contact || templateContext?.intro_contact || '',
    contact_name: templateContext?.contact_name || '',
    contact_phone: templateContext?.contact_phone || '',
  }

  let message = template
  for (const [key, value] of Object.entries(context)) {
    const moustache = new RegExp(`{{\\s*${key}\\s*}}`, 'g')
    const braces = new RegExp(`\\{${key}\\}`, 'g')
    message = message.replace(moustache, value).replace(braces, value)
  }

  return message
    .replace(/\[Имя\]/g, firstName)
    .replace(/\[Дата\]/g, formattedDate)
    .replace(/\[Время\]/g, timeStr)
}

export function buildIntroDayFallback(candidateFio: string, dateStr: string, timeStr: string): string {
  const firstName = introDayFirstName(candidateFio)
  const formattedDate = formatIntroDayDate(dateStr)
  return `Здравствуйте, ${firstName}. Приглашаем вас на ознакомительный день ${formattedDate} в ${timeStr}. Подтвердите, пожалуйста, что сможете присутствовать.`
}

export function getTomorrowDate(): string {
  const next = new Date()
  next.setDate(next.getDate() + 1)
  return next.toISOString().slice(0, 10)
}

export function threadAvatar(thread?: CandidateChatThread | null): string {
  return (thread?.title || 'К').slice(0, 2).toUpperCase()
}

export function groupedMessagesWithUnread(
  messages: CandidateChatMessage[],
  unreadCount: number,
): GroupedMessageRow[] {
  const groups: GroupedMessageRow[] = []
  const inboundIds = messages.filter((message) => message.direction === 'inbound').map((message) => message.id)
  const firstUnreadId = unreadCount > 0 ? inboundIds[Math.max(0, inboundIds.length - unreadCount)] : null
  let currentDayKey = ''
  for (const message of messages) {
    const dayKey = new Date(message.created_at).toDateString()
    if (dayKey !== currentDayKey) {
      currentDayKey = dayKey
      groups.push({ type: 'divider', key: `${dayKey}-${message.id}`, label: formatDayLabel(message.created_at) })
    }
    groups.push({ type: 'message', message, unreadAnchor: firstUnreadId === message.id })
  }
  return groups
}
