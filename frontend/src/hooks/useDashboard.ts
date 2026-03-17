import { useCallback } from 'react'
import { api } from '../api/client'
import { useTaskStore } from '../store/taskStore'

/**
 * Returns a refresh function for fetching dashboard data.
 * Does NOT set up WebSocket — that's done once in App.tsx via useWebSocket.
 */
export function useDashboard() {
  const { setDashboard, setLoading } = useTaskStore()

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getDashboard()
      setDashboard(data)
    } catch (err) {
      console.error('Failed to fetch dashboard:', err)
    } finally {
      setLoading(false)
    }
  }, [setDashboard, setLoading])

  return { refresh }
}
