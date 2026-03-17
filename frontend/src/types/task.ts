export interface Task {
  id: string
  title: string
  description?: string
  sender: string
  due_hint?: string
  next_step?: string
  teams_link?: string
  source_link?: string
  source: string
  source_metadata?: {
    meeting_title?: string
    alternate_links?: { source: string; link: string }[]
  }
  source_context?: string
  direction: 'inbound' | 'outbound'
  thread_id?: string
  state: 'open' | 'waiting' | 'needs_followup' | 'likely_done' | 'closed'
  state_history: { state: string; reason: string; date: string }[]
  score: number
  score_breakdown: Record<string, number>
  times_seen: number
  created: string
  updated: string
  parent_id?: string | null
  subtask_ids: string[]
  closed_by?: string
  user_priority?: number

  // Computed fields from viewmodel
  _idle_days: number
  _age: string
  _confidence: number
  _next_action: string
  _focus_priority: number
  _task_type: string
  _task_type_info: { emoji: string; label: string; keywords: string[] }
  _source_context: string
  _is_pinned: boolean
  _links: TaskLink[]
  _due_date?: string | null
  _is_overdue: boolean
}

export interface TaskLink {
  label: string
  url: string
  source: string
  fallback?: string
}

export interface TaskGroup {
  key: string
  title: string
  source_type: string
  source_link: string
  tasks: Task[]
}

export interface DashboardStats {
  focus_count: number
  due_soon_count: number
  nudge_count: number
  stale_count: number
  open_count: number
  total_tasks: number
  total_closed: number
  sync_health: string
  last_synced: string
}

export interface DashboardSections {
  pinned: Task[]
  focus: Task[]
  due_soon: Task[]
  open: {
    groups: TaskGroup[]
    ungrouped: Task[]
  }
  stale: Task[]
  nudge: Task[]
  waiting_outbound: Task[]
  closed_by_me: Task[]
  recently_closed: Task[]
}

export interface DashboardData {
  stats: DashboardStats
  sections: DashboardSections
  run_stats: Record<string, number>
  timestamp: string
}
