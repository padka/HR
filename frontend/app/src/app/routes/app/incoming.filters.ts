export type IncomingStatusFilter =
  | 'all'
  | 'waiting_slot'
  | 'stalled_waiting_slot'
  | 'slot_pending'
  | 'requested_other_time'

export type IncomingOwnerFilter = 'all' | 'mine' | 'assigned' | 'unassigned'
export type IncomingWaitingFilter = 'all' | '24h' | '48h'
export type IncomingAiFilter = 'all' | 'high' | 'medium' | 'low' | 'unknown'
export type IncomingSortMode = 'priority' | 'waiting_desc' | 'recent_desc' | 'ai_score_desc' | 'name_asc'

export type IncomingPersistedFilters = {
  search: string
  cityFilter: string
  statusFilter: IncomingStatusFilter
  ownerFilter: IncomingOwnerFilter
  waitingFilter: IncomingWaitingFilter
  aiFilter: IncomingAiFilter
  sortMode: IncomingSortMode
  showAdvancedFilters: boolean
}

export const INCOMING_FILTERS_STORAGE_KEY = 'recruitsmart:incoming:filters:v1'

const STATUS_FILTERS: IncomingStatusFilter[] = [
  'all',
  'waiting_slot',
  'stalled_waiting_slot',
  'slot_pending',
  'requested_other_time',
]
const OWNER_FILTERS: IncomingOwnerFilter[] = ['all', 'mine', 'assigned', 'unassigned']
const WAITING_FILTERS: IncomingWaitingFilter[] = ['all', '24h', '48h']
const AI_FILTERS: IncomingAiFilter[] = ['all', 'high', 'medium', 'low', 'unknown']
const SORT_MODES: IncomingSortMode[] = ['priority', 'waiting_desc', 'recent_desc', 'ai_score_desc', 'name_asc']

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function pickEnum<T extends string>(value: unknown, options: readonly T[], fallback: T): T {
  return typeof value === 'string' && options.includes(value as T) ? (value as T) : fallback
}

function pickString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function pickBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

export function parseIncomingPersistedFilters(raw: string | null): Partial<IncomingPersistedFilters> {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    if (!isObject(parsed)) return {}
    return {
      search: pickString(parsed.search, ''),
      cityFilter: pickString(parsed.cityFilter, 'all'),
      statusFilter: pickEnum(parsed.statusFilter, STATUS_FILTERS, 'all'),
      ownerFilter: pickEnum(parsed.ownerFilter, OWNER_FILTERS, 'all'),
      waitingFilter: pickEnum(parsed.waitingFilter, WAITING_FILTERS, 'all'),
      aiFilter: pickEnum(parsed.aiFilter, AI_FILTERS, 'all'),
      sortMode: pickEnum(parsed.sortMode, SORT_MODES, 'priority'),
      showAdvancedFilters: pickBoolean(parsed.showAdvancedFilters, false),
    }
  } catch {
    return {}
  }
}

export function loadIncomingPersistedFilters(
  storage: Pick<Storage, 'getItem'> | null,
  key: string = INCOMING_FILTERS_STORAGE_KEY,
): Partial<IncomingPersistedFilters> {
  if (!storage) return {}
  return parseIncomingPersistedFilters(storage.getItem(key))
}

export function saveIncomingPersistedFilters(
  storage: Pick<Storage, 'setItem'> | null,
  payload: IncomingPersistedFilters,
  key: string = INCOMING_FILTERS_STORAGE_KEY,
): void {
  if (!storage) return
  storage.setItem(key, JSON.stringify(payload))
}

export function clearIncomingPersistedFilters(
  storage: Pick<Storage, 'removeItem'> | null,
  key: string = INCOMING_FILTERS_STORAGE_KEY,
): void {
  if (!storage) return
  storage.removeItem(key)
}
