export function normalizeTelegramUsername(username?: string | null): string | null {
  if (!username) return null
  const cleaned = username.trim().replace(/^@/, '')
  return cleaned || null
}

export function normalizeConferenceUrl(url?: string | null): string | null {
  if (!url) return null
  const raw = url.trim()
  if (!raw) return null
  try {
    const prepared = raw.includes('://') ? raw : `https://${raw}`
    const parsed = new URL(prepared)
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    return parsed.toString()
  } catch {
    return null
  }
}
