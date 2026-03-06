import { useEffect } from 'react'
import { create } from 'zustand'

const MOBILE_QUERY = '(max-width: 768px)'

const resolveIsMobile = () => {
  if (typeof window === 'undefined') return false
  const byWidth = window.innerWidth <= 768
  if (typeof window.matchMedia !== 'function') return byWidth
  return window.matchMedia(MOBILE_QUERY).matches || byWidth
}

type MobileState = {
  isMobile: boolean
  initialized: boolean
  setIsMobile: (isMobile: boolean) => void
  setInitialized: (initialized: boolean) => void
}

const getInitialIsMobile = () => {
  return resolveIsMobile()
}

const useIsMobileStore = create<MobileState>((set) => ({
  isMobile: getInitialIsMobile(),
  initialized: false,
  setIsMobile: (isMobile) => set({ isMobile }),
  setInitialized: (initialized) => set({ initialized }),
}))

let detachListener: (() => void) | null = null

function ensureListener() {
  if (typeof window === 'undefined') return () => {}
  if (detachListener) return detachListener

  const sync = () => {
    useIsMobileStore.getState().setIsMobile(resolveIsMobile())
  }

  sync()
  window.addEventListener('resize', sync, { passive: true })

  if (typeof window.matchMedia === 'function') {
    const media = window.matchMedia(MOBILE_QUERY)
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', sync)
      detachListener = () => {
        media.removeEventListener('change', sync)
        window.removeEventListener('resize', sync)
      }
      return detachListener
    }

    const legacyMedia = media as MediaQueryList & {
      addListener?: (listener: (this: MediaQueryList, ev: MediaQueryListEvent) => unknown) => void
      removeListener?: (listener: (this: MediaQueryList, ev: MediaQueryListEvent) => unknown) => void
    }

    if (typeof legacyMedia.addListener === 'function') {
      legacyMedia.addListener(sync)
      detachListener = () => {
        legacyMedia.removeListener?.(sync)
        window.removeEventListener('resize', sync)
      }
      return detachListener
    }
  }

  detachListener = () => window.removeEventListener('resize', sync)
  return detachListener
}

export function useIsMobile() {
  const isMobile = useIsMobileStore((state) => state.isMobile)
  const initialized = useIsMobileStore((state) => state.initialized)
  const setInitialized = useIsMobileStore((state) => state.setInitialized)

  useEffect(() => {
    ensureListener()
    if (!initialized) setInitialized(true)
  }, [initialized, setInitialized])

  return isMobile
}

export default useIsMobile
