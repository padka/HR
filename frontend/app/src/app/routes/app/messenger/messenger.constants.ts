export const THREAD_LIMIT = 120
export const MESSAGE_LIMIT = 120
export const URL_RE = /(https?:\/\/[^\s]+)/gi

export const CONFIRMED_SLOT_STATUSES = new Set([
  'CONFIRMED',
  'CONFIRMED_BY_CANDIDATE',
  'RESCHEDULE_CONFIRMED',
  'COMPLETED',
])
