import { useEffect, useRef } from 'react'

export function useWebSocket(onMessage: (data: any) => void) {
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number>()
  const attemptRef = useRef(0)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return
      if (wsRef.current?.readyState === WebSocket.OPEN) return

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

      ws.onopen = () => {
        attemptRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessageRef.current(data)
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        wsRef.current = null
        if (!mountedRef.current) return
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        const delay = Math.min(1000 * Math.pow(2, attemptRef.current), 30000)
        attemptRef.current++
        reconnectTimer.current = window.setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }

      wsRef.current = ws
    }

    connect()

    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, []) // Empty deps — stable across renders
}
