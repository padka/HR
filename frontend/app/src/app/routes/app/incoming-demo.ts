export type IncomingCandidateLike = {
  id: number
  name?: string | null
  city?: string | null
  city_id?: number | null
  status_display?: string | null
  status_slug?: string | null
  waiting_hours?: number | null
  availability_window?: string | null
  availability_note?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  last_message?: string | null
  last_message_at?: string | null
  responsible_recruiter_id?: number | null
  responsible_recruiter_name?: string | null
  ai_relevance_score?: number | null
  ai_relevance_level?: 'high' | 'medium' | 'low' | 'unknown' | null
  requested_another_time?: boolean
  requested_another_time_at?: string | null
  requested_another_time_comment?: string | null
  incoming_substatus?: string | null
}

export type IncomingCityOption = {
  id: number
  name: string
}

const FALLBACK_CITIES: IncomingCityOption[] = [
  { id: 10, name: 'Москва' },
  { id: 11, name: 'Ростов' },
  { id: 12, name: 'Сочи' },
  { id: 7, name: 'Новосибирск' },
  { id: 16, name: 'Волгоград' },
  { id: 18, name: 'Алматы' },
]

const FIRST_NAMES = [
  'Иван',
  'Павел',
  'Денис',
  'Марина',
  'Екатерина',
  'Олег',
  'Роман',
  'Кирилл',
  'Тимур',
  'Анна',
]

const LAST_NAMES = [
  'Петров',
  'Ильин',
  'Смирнов',
  'Киселев',
  'Мартынов',
  'Зайцев',
  'Шевченко',
  'Орлов',
  'Ковалев',
  'Федорова',
]

const AVAILABILITY_WINDOWS = [
  'утро 09:00–12:00',
  'день 12:00–16:00',
  'вечер 16:00–20:00',
  'любой слот после 11:00',
]

const GENERAL_NOTES = [
  'Готов быстро выйти на обучение',
  'Просил детальнее рассказать про график',
  'В приоритете офис рядом с метро',
  'Уточняет формат первого дня',
  'Ждет подтверждения времени',
]

const REQUESTED_TIME_NOTES = [
  'Сможет только после 18:00',
  'Просит перенести на завтра после обеда',
  'Не успевает к текущему слоту, нужен более поздний',
  'Подтверждает интервью, но просит утренний слот',
]

const RECRUITER_NAMES = [
  'Юлия',
  'Михаил',
  'Алина',
  'Сергей',
]

const STATUSES = [
  { slug: 'waiting_slot', display: 'Ожидает слот', requested: false },
  { slug: 'slot_pending', display: 'На согласовании', requested: false },
  { slug: 'stalled_waiting_slot', display: 'Застрял в очереди', requested: false },
  { slug: 'slot_pending', display: 'На согласовании', requested: true },
] as const

function parsePositiveInt(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0
}

function normalizeHost(value: string | undefined): string {
  return String(value || '').trim().toLowerCase()
}

function buildName(index: number): string {
  const first = FIRST_NAMES[index % FIRST_NAMES.length]
  const last = LAST_NAMES[Math.floor(index / FIRST_NAMES.length) % LAST_NAMES.length]
  return `${first} ${last}`
}

function selectCity(cityOptions: IncomingCityOption[], index: number): IncomingCityOption {
  if (!cityOptions.length) return FALLBACK_CITIES[index % FALLBACK_CITIES.length]
  return cityOptions[index % cityOptions.length]
}

export function resolveIncomingDemoCount(params?: {
  envValue?: string | number
  hostname?: string
  search?: string
}): number {
  const fromEnv = parsePositiveInt(params?.envValue)
  if (fromEnv > 0) return fromEnv

  const search = String(params?.search || '')
  if (search) {
    const query = new URLSearchParams(search)
    const fromQuery = parsePositiveInt(query.get('incoming_demo_count'))
    if (fromQuery > 0) return fromQuery
  }

  const host = normalizeHost(params?.hostname)
  if (host.includes('test') || host.includes('staging')) {
    return 100
  }

  return 0
}

export function withDemoIncomingCandidates<T extends IncomingCandidateLike>(
  items: T[],
  options: {
    targetCount: number
    cityOptions?: IncomingCityOption[]
  },
): T[] {
  const targetCount = parsePositiveInt(options.targetCount)
  if (targetCount <= 0 || items.length >= targetCount) return items

  const cityOptions = options.cityOptions && options.cityOptions.length ? options.cityOptions : FALLBACK_CITIES
  const firstTemplate = (items[0] || {}) as Partial<T>
  const next = [...items]
  const now = Date.now()

  for (let index = items.length; index < targetCount; index += 1) {
    const city = selectCity(cityOptions, index)
    const status = STATUSES[index % STATUSES.length]
    const waitingHours =
      status.slug === 'stalled_waiting_slot'
        ? 24 + (index % 72)
        : status.slug === 'slot_pending'
          ? 2 + (index % 14)
          : 1 + (index % 9)
    const requestedAt = new Date(now - (index + 3) * 23 * 60 * 1000).toISOString()
    const lastMessageAt = new Date(now - (index + 1) * 11 * 60 * 1000).toISOString()
    const aiLevels: Array<'high' | 'medium' | 'low' | 'unknown'> = ['high', 'medium', 'low', 'unknown']
    const aiLevel = aiLevels[index % aiLevels.length]
    const aiScore = aiLevel === 'unknown' ? null : 36 + ((index * 7) % 58)
    const recruiterName = RECRUITER_NAMES[index % RECRUITER_NAMES.length]
    const requestedComment = status.requested ? REQUESTED_TIME_NOTES[index % REQUESTED_TIME_NOTES.length] : null

    const synthetic = {
      ...firstTemplate,
      id: 900_000 + index,
      name: buildName(index),
      city: city.name,
      city_id: city.id,
      status_slug: status.slug,
      status_display: status.display,
      waiting_hours: waitingHours,
      availability_window: AVAILABILITY_WINDOWS[index % AVAILABILITY_WINDOWS.length],
      availability_note: GENERAL_NOTES[index % GENERAL_NOTES.length],
      telegram_id: 700_000_000 + index,
      telegram_username: `candidate_${index + 1}`,
      last_message: status.requested
        ? `Просьба о переносе: ${requestedComment}`
        : `Сообщение кандидата: ${GENERAL_NOTES[(index + 2) % GENERAL_NOTES.length]}`,
      last_message_at: lastMessageAt,
      responsible_recruiter_id: 700 + (index % RECRUITER_NAMES.length),
      responsible_recruiter_name: recruiterName,
      ai_relevance_level: aiLevel,
      ai_relevance_score: aiScore,
      requested_another_time: status.requested,
      requested_another_time_at: status.requested ? requestedAt : null,
      requested_another_time_comment: requestedComment,
      incoming_substatus: status.requested ? 'requested_other_time' : null,
    } as T

    next.push(synthetic)
  }

  return next
}

