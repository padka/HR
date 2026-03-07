import { useQuery } from '@tanstack/react-query'
import { fetchProfile, profileQueryKey, type ProfileResponse } from '@/api/services/profile'

export type { ProfileResponse } from '@/api/services/profile'

export function useProfile(enabled = true) {
  return useQuery<ProfileResponse>({
    queryKey: profileQueryKey,
    queryFn: fetchProfile,
    staleTime: 15_000,
    enabled,
  })
}
