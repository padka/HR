import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

interface SlotChangeEvent {
  type: 'slot_change'
  change_type: 'created' | 'updated' | 'deleted'
  slot_id: number
  recruiter_id: number | null
  slot: Record<string, unknown>
  timestamp: string
}

type WebSocketMessage = SlotChangeEvent

interface UseCalendarWebSocketOptions {
  enabled?: boolean
  onSlotChange?: (event: SlotChangeEvent) => void
}

export function useCalendarWebSocket(options: UseCalendarWebSocketOptions = {}) {
  const { enabled = true, onSlotChange } = options
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttempts = useRef(0)
  const DEBUG = import.meta.env.DEV

  const debugLog = useCallback(
    (level: 'log' | 'warn' | 'error', ...args: unknown[]) => {
      if (!DEBUG) return
      console[level]('[CalendarWS]', ...args)
    },
    [DEBUG],
  )

  const connect = useCallback(() => {
    if (!enabled) return

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/calendar`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        debugLog('log', 'Connected')
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketMessage

          if (data.type === 'slot_change') {
            debugLog('log', 'Slot change:', data.change_type, data.slot_id)

            // Invalidate calendar queries to refetch data
            queryClient.invalidateQueries({ queryKey: ['calendar-events'] })

            // Also invalidate dashboard calendar for backward compatibility
            queryClient.invalidateQueries({ queryKey: ['dashboard-calendar'] })

            // Call custom handler if provided
            if (onSlotChange) {
              onSlotChange(data)
            }
          }
        } catch (err) {
          debugLog('error', 'Failed to parse message:', err)
        }
      }

      ws.onerror = (error) => {
        debugLog('error', 'Error:', error)
      }

      ws.onclose = (event) => {
        debugLog('log', 'Disconnected:', event.code, event.reason)
        wsRef.current = null

        if (event.code === 1008 || event.code === 4401) {
          debugLog('warn', 'Authorization required, reconnect disabled')
          return
        }

        // Attempt to reconnect with exponential backoff
        if (enabled && reconnectAttempts.current < 5) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          debugLog('log', `Reconnecting in ${delay}ms...`)
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        }
      }
    } catch (err) {
      debugLog('error', 'Failed to connect:', err)
    }
  }, [debugLog, enabled, queryClient, onSlotChange])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // Reconnect when enabled changes
  useEffect(() => {
    if (enabled && !wsRef.current) {
      connect()
    } else if (!enabled && wsRef.current) {
      disconnect()
    }
  }, [enabled, connect, disconnect])

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    reconnect: connect,
    disconnect,
  }
}

export default useCalendarWebSocket
