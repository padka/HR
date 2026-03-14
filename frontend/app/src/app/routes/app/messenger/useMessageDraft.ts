import { useEffect, useState } from 'react'

const DRAFT_STORAGE_PREFIX = 'candidate-chat-draft:'

function readDraft(candidateId: number | null): string {
  if (candidateId == null || typeof window === 'undefined') return ''
  return window.localStorage.getItem(`${DRAFT_STORAGE_PREFIX}${candidateId}`) || ''
}

export function useMessageDraft(candidateId: number | null) {
  const [draft, setDraft] = useState('')

  useEffect(() => {
    setDraft(readDraft(candidateId))
  }, [candidateId])

  useEffect(() => {
    if (candidateId == null || typeof window === 'undefined') return
    window.localStorage.setItem(`${DRAFT_STORAGE_PREFIX}${candidateId}`, draft)
  }, [candidateId, draft])

  return { draft, setDraft }
}
