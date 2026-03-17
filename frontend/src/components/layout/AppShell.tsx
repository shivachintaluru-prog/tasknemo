import { ReactNode } from 'react'
import { Header } from './Header'
import { TabNav } from './TabNav'
import { TaskDetailPanel } from '../task/TaskDetailPanel'
import { useTaskStore } from '../../store/taskStore'

interface Props {
  children: ReactNode
  onRefresh: () => void
}

export function AppShell({ children, onRefresh }: Props) {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId)

  return (
    <div className="min-h-screen bg-cream">
      <Header onRefresh={onRefresh} />
      <div className="max-w-dashboard mx-auto px-4 pt-2 pb-24">
        <TabNav />
        {children}
      </div>
      {selectedTaskId && <TaskDetailPanel />}
    </div>
  )
}
