import { apiFetch } from '@/api/client'

export type CandidateSearchItem = {
  id: number
  candidate_id: string
  fio?: string | null
  city?: string | null
  telegram_id?: number | null
  status?: { slug?: string; label?: string }
}

export type CandidateSearchPayload = {
  items: CandidateSearchItem[]
}

export type SlotsBulkActionPayload = {
  action: string
  slot_ids: number[]
  force?: boolean
}

export function fetchSlots<T>(queryString: string) {
  return apiFetch<T>(`/slots?${queryString}`)
}

export function searchSlotCandidates(search: string, perPage = 10) {
  return apiFetch<CandidateSearchPayload>(`/candidates?search=${encodeURIComponent(search)}&per_page=${perPage}`)
}

export function assignCandidateToSlot(candidateId: number, slotId: number) {
  return apiFetch(`/candidates/${candidateId}/schedule-slot`, {
    method: 'POST',
    body: JSON.stringify({ slot_id: slotId }),
  })
}

export function rescheduleSlot(
  slotId: number,
  payload: { date: string; time: string; reason?: string | null },
) {
  return apiFetch(`/slots/${slotId}/reschedule`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function rejectSlotBooking(slotId: number) {
  return apiFetch(`/slots/${slotId}/reject_booking`, { method: 'POST' })
}

export function deleteSlot(slotId: number) {
  return apiFetch<{ ok?: boolean; message?: string }>(`/slots/${slotId}`, { method: 'DELETE' })
}

export function submitSlotsBulkAction(payload: SlotsBulkActionPayload) {
  return apiFetch('/slots/bulk', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
