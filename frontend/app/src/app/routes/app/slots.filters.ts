import type { SlotStatusFilter } from './slots.utils'

export type SlotSortField = 'recruiter_time' | 'region_time' | 'city' | 'candidate' | 'status' | 'type'
export type SlotSortDir = 'asc' | 'desc'

export type SlotsPersistedFilters = {
  statusFilter: SlotStatusFilter
  purposeFilter: string
  search: string
  cityFilter: string
  recruiterFilter: string
  candidateFilter: 'all' | 'with' | 'without'
  tzRelationFilter: 'all' | 'same' | 'diff'
  dateFrom: string
  dateTo: string
  sortField: SlotSortField
  sortDir: SlotSortDir
  limit: number
  page: number
  perPage: number
}

export const SLOTS_FILTERS_STORAGE_KEY = 'recruitsmart:slots:filters:v1'

const STATUS_FILTERS: SlotStatusFilter[] = ['ALL', 'FREE', 'PENDING', 'BOOKED', 'CONFIRMED_BY_CANDIDATE']
const SORT_FIELDS: SlotSortField[] = ['recruiter_time', 'region_time', 'city', 'candidate', 'status', 'type']
const SORT_DIRS: SlotSortDir[] = ['asc', 'desc']
const PURPOSE_FILTERS = ['all', 'interview', 'intro_day']
const CANDIDATE_FILTERS: Array<'all' | 'with' | 'without'> = ['all', 'with', 'without']
const TZ_RELATION_FILTERS: Array<'all' | 'same' | 'diff'> = ['all', 'same', 'diff']
const LIMIT_VALUES = [100, 300, 500]
const PER_PAGE_VALUES = [10, 20, 50, 100]

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function pickEnum<T extends string>(value: unknown, options: readonly T[], fallback: T): T {
  return typeof value === 'string' && options.includes(value as T) ? (value as T) : fallback
}

function pickString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function pickNumber(value: unknown, options: readonly number[], fallback: number): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return fallback
  return options.includes(value) ? value : fallback
}

function pickPositiveInt(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  const normalized = Math.floor(value)
  return normalized > 0 ? normalized : fallback
}

export function parseSlotsPersistedFilters(raw: string | null): Partial<SlotsPersistedFilters> {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    if (!isObject(parsed)) return {}
    return {
      statusFilter: pickEnum(parsed.statusFilter, STATUS_FILTERS, 'ALL'),
      purposeFilter: pickEnum(parsed.purposeFilter, PURPOSE_FILTERS, 'all'),
      search: pickString(parsed.search, ''),
      cityFilter: pickString(parsed.cityFilter, 'all'),
      recruiterFilter: pickString(parsed.recruiterFilter, 'all'),
      candidateFilter: pickEnum(parsed.candidateFilter, CANDIDATE_FILTERS, 'all'),
      tzRelationFilter: pickEnum(parsed.tzRelationFilter, TZ_RELATION_FILTERS, 'all'),
      dateFrom: pickString(parsed.dateFrom, ''),
      dateTo: pickString(parsed.dateTo, ''),
      sortField: pickEnum(parsed.sortField, SORT_FIELDS, 'recruiter_time'),
      sortDir: pickEnum(parsed.sortDir, SORT_DIRS, 'desc'),
      limit: pickNumber(parsed.limit, LIMIT_VALUES, 500),
      page: pickPositiveInt(parsed.page, 1),
      perPage: pickNumber(parsed.perPage, PER_PAGE_VALUES, 20),
    }
  } catch {
    return {}
  }
}

export function loadSlotsPersistedFilters(
  storage: Pick<Storage, 'getItem'> | null,
  key: string = SLOTS_FILTERS_STORAGE_KEY,
): Partial<SlotsPersistedFilters> {
  if (!storage) return {}
  return parseSlotsPersistedFilters(storage.getItem(key))
}

export function saveSlotsPersistedFilters(
  storage: Pick<Storage, 'setItem'> | null,
  payload: SlotsPersistedFilters,
  key: string = SLOTS_FILTERS_STORAGE_KEY,
): void {
  if (!storage) return
  storage.setItem(key, JSON.stringify(payload))
}

export function clearSlotsPersistedFilters(
  storage: Pick<Storage, 'removeItem'> | null,
  key: string = SLOTS_FILTERS_STORAGE_KEY,
): void {
  if (!storage) return
  storage.removeItem(key)
}
