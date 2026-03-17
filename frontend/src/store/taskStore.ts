import { create } from 'zustand'
import type { DashboardData, Task } from '../types/task'

interface TaskStore {
  dashboard: DashboardData | null
  loading: boolean
  selectedTaskId: string | null
  searchQuery: string
  activeTab: 'dashboard' | 'analytics' | 'settings'
  setDashboard: (data: DashboardData) => void
  setLoading: (loading: boolean) => void
  selectTask: (id: string | null) => void
  setSearch: (query: string) => void
  setActiveTab: (tab: 'dashboard' | 'analytics' | 'settings') => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  dashboard: null,
  loading: true,
  selectedTaskId: null,
  searchQuery: '',
  activeTab: 'dashboard',
  setDashboard: (data) => set({ dashboard: data }),
  setLoading: (loading) => set({ loading }),
  selectTask: (id) => set({ selectedTaskId: id }),
  setSearch: (query) => set({ searchQuery: query }),
  setActiveTab: (tab) => set({ activeTab: tab }),
}))
