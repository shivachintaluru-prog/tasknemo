import { useEffect, useCallback } from 'react'
import { useTaskStore } from './store/taskStore'
import { useDashboard } from './hooks/useDashboard'
import { useWebSocket } from './hooks/useWebSocket'
import { AppShell } from './components/layout/AppShell'
import { DashboardPage } from './components/dashboard/DashboardPage'
import { AnalyticsPage } from './components/analytics/AnalyticsPage'
import { SettingsPage } from './components/settings/SettingsPage'

export default function App() {
  const { activeTab, loading, dashboard } = useTaskStore()
  const { refresh } = useDashboard()

  // Single WebSocket connection for the entire app
  const onWsMessage = useCallback((data: any) => {
    if (data.type === 'data_changed') {
      refresh()
    }
  }, [refresh])

  useWebSocket(onWsMessage)

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <AppShell onRefresh={refresh}>
      {loading && !dashboard ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-3 border-purple/30 border-t-purple rounded-full animate-spin" />
            <span className="text-sm text-gray-400 font-mono">Loading tasks...</span>
          </div>
        </div>
      ) : (
        <>
          {activeTab === 'dashboard' && <DashboardPage />}
          {activeTab === 'analytics' && <AnalyticsPage />}
          {activeTab === 'settings' && <SettingsPage />}
        </>
      )}
    </AppShell>
  )
}
