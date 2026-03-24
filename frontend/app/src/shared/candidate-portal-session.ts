const CANDIDATE_PORTAL_TOKEN_STORAGE_KEY = 'candidate-portal:access-token'

function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function readCandidatePortalAccessToken(): string {
  const storage = getStorage()
  if (!storage) return ''
  try {
    return (storage.getItem(CANDIDATE_PORTAL_TOKEN_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

export function writeCandidatePortalAccessToken(token: string): void {
  const storage = getStorage()
  if (!storage) return
  const next = token.trim()
  try {
    if (next) {
      storage.setItem(CANDIDATE_PORTAL_TOKEN_STORAGE_KEY, next)
    } else {
      storage.removeItem(CANDIDATE_PORTAL_TOKEN_STORAGE_KEY)
    }
  } catch {
    // Ignore storage failures in constrained webviews.
  }
}

export function clearCandidatePortalAccessToken(): void {
  writeCandidatePortalAccessToken('')
}
