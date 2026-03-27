const CANDIDATE_PORTAL_TOKEN_STORAGE_KEY = 'candidate-portal:access-token'
const CANDIDATE_PORTAL_ENTRY_STORAGE_KEY = 'candidate-portal:entry-token'

function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

function getPersistentStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
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

export function readCandidatePortalEntryToken(): string {
  const storage = getPersistentStorage()
  if (!storage) return ''
  try {
    return (storage.getItem(CANDIDATE_PORTAL_ENTRY_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

export function writeCandidatePortalEntryToken(token: string): void {
  const storage = getPersistentStorage()
  if (!storage) return
  const next = token.trim()
  try {
    if (next) {
      storage.setItem(CANDIDATE_PORTAL_ENTRY_STORAGE_KEY, next)
    } else {
      storage.removeItem(CANDIDATE_PORTAL_ENTRY_STORAGE_KEY)
    }
  } catch {
    // Ignore storage failures in constrained webviews.
  }
}

export function clearCandidatePortalEntryToken(): void {
  writeCandidatePortalEntryToken('')
}

export function extractCandidatePortalEntryToken(entryUrl?: string | null): string {
  const raw = String(entryUrl || '').trim()
  if (!raw) return ''
  try {
    const base =
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'https://candidate.local'
    return (new URL(raw, base).searchParams.get('entry') || '').trim()
  } catch {
    const match = raw.match(/[?&]entry=([^&#]+)/)
    if (!match?.[1]) return ''
    try {
      return decodeURIComponent(match[1]).trim()
    } catch {
      return match[1].trim()
    }
  }
}

export function persistCandidatePortalEntryTokenFromUrl(entryUrl?: string | null): string {
  const token = extractCandidatePortalEntryToken(entryUrl)
  if (token) {
    writeCandidatePortalEntryToken(token)
  }
  return token
}
