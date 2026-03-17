import { useTaskStore } from '../../store/taskStore'
import { api } from '../../api/client'
import { useDashboard } from '../../hooks/useDashboard'
import { ScoreBreakdown } from './ScoreBreakdown'
import { StateTimeline } from './StateTimeline'
import type { Task } from '../../types/task'

const PRIORITY_OPTIONS = [
  { value: 20, label: 'High', color: 'bg-accent-red text-white' },
  { value: 10, label: 'Medium', color: 'bg-accent-orange text-white' },
  { value: 0, label: 'Low', color: 'bg-gray-200 text-gray-600' },
]

function findTask(dashboard: any, taskId: string): Task | null {
  if (!dashboard) return null
  const { sections } = dashboard
  const allSections = [
    sections.pinned, sections.focus, sections.due_soon,
    ...sections.open.groups.map((g: any) => g.tasks),
    sections.open.ungrouped,
    sections.stale, sections.nudge, sections.waiting_outbound,
    sections.closed_by_me, sections.recently_closed,
  ]
  for (const arr of allSections) {
    const found = arr.find((t: Task) => t.id === taskId)
    if (found) return found
  }
  return null
}

export function TaskDetailPanel() {
  const { selectedTaskId, selectTask, dashboard } = useTaskStore()
  const { refresh } = useDashboard()

  if (!selectedTaskId || !dashboard) return null
  const task = findTask(dashboard, selectedTaskId)
  if (!task) return null

  const isClosed = task.state === 'closed'
  const currentPriority = task.user_priority || 0

  const handleClose = async () => {
    await api.closeTask(task.id)
    refresh()
  }

  const handleReopen = async () => {
    await api.reopenTask(task.id)
    refresh()
  }

  const handlePin = async () => {
    if (task._is_pinned) {
      await api.unpinTask(task.id)
    } else {
      await api.pinTask(task.id)
    }
    refresh()
  }

  const handlePriority = async (value: number) => {
    await api.updateTask(task.id, { user_priority: value })
    refresh()
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/10 z-40"
        onClick={() => selectTask(null)}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 bottom-0 w-[400px] bg-white shadow-xl z-50 animate-slide-in overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-100 px-5 py-4 flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs text-gray-400">{task.id}</span>
              <span className={`
                px-1.5 py-0.5 rounded text-[10px] font-bold
                ${task.state === 'open' ? 'bg-purple/10 text-purple' :
                  task.state === 'closed' ? 'bg-accent-green/10 text-accent-green' :
                  task.state === 'waiting' ? 'bg-accent-orange/10 text-accent-orange' :
                  'bg-gray-100 text-gray-500'}
              `}>
                {task.state}
              </span>
              {task._is_pinned && <span className="text-xs">{'\uD83D\uDCCC'}</span>}
            </div>
            <h2 className="text-lg font-bold text-gray-800 leading-snug">{task.title}</h2>
          </div>
          <button
            onClick={() => selectTask(null)}
            className="p-1 rounded-md hover:bg-gray-100 transition-colors shrink-0"
          >
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-5">
          {/* Priority selector */}
          {!isClosed && (
            <div>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Priority</h3>
              <div className="flex gap-2">
                {PRIORITY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => handlePriority(opt.value)}
                    className={`
                      px-3 py-1.5 rounded-lg text-xs font-bold transition-all
                      ${currentPriority === opt.value
                        ? opt.color + ' ring-2 ring-offset-1 ring-gray-300'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }
                    `}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <MetaField label="Sender" value={task.sender} />
            <MetaField label="Direction" value={task.direction} />
            <MetaField label="Source" value={task.source} />
            <MetaField label="Age" value={task._age} />
            <MetaField label="Idle" value={`${task._idle_days}d`} />
            <MetaField label="Confidence" value={`${Math.round(task._confidence * 100)}%`} />
            {task.due_hint && <MetaField label="Due" value={task.due_hint} highlight={task._is_overdue} />}
            <MetaField label="Type" value={task._task_type_info?.label || task._task_type} />
          </div>

          {/* Description */}
          {task.description && (
            <div>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Description</h3>
              <p className="text-sm text-gray-700 leading-relaxed">{task.description}</p>
            </div>
          )}

          {/* Next Action */}
          {task._next_action && !isClosed && (
            <div>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Next Action</h3>
              <div className="flex items-center gap-2">
                <span className="px-2 py-1 rounded bg-purple/10 text-purple text-xs font-semibold">next</span>
                <span className="text-sm text-gray-700">{task._next_action}</span>
              </div>
            </div>
          )}

          {/* Score Breakdown */}
          <ScoreBreakdown task={task} />

          {/* State Timeline */}
          <StateTimeline task={task} />

          {/* Links */}
          {task._links && task._links.length > 0 && (
            <div>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Links</h3>
              <div className="space-y-1.5">
                {task._links.map((link, i) => (
                  link.url ? (
                    <a
                      key={i}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-sm text-purple hover:underline"
                    >
                      {link.label} {'\u2197'}
                    </a>
                  ) : link.fallback ? (
                    <span key={i} className="block text-sm text-gray-400 italic">{link.fallback}</span>
                  ) : null
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="sticky bottom-0 bg-white border-t border-gray-100 px-5 py-3 flex gap-2">
          <button onClick={handlePin} className="flex-1 px-3 py-2 text-sm font-semibold rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
            {task._is_pinned ? 'Unpin' : 'Pin'}
          </button>
          {!isClosed ? (
            <button onClick={handleClose} className="flex-1 px-3 py-2 text-sm font-bold rounded-lg bg-accent-green text-white hover:bg-accent-green/90 transition-colors">
              Close Task
            </button>
          ) : (
            <button onClick={handleReopen} className="flex-1 px-3 py-2 text-sm font-bold rounded-lg bg-purple text-white hover:bg-purple-dark transition-colors">
              Reopen
            </button>
          )}
        </div>
      </div>
    </>
  )
}

function MetaField({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <span className="text-[10px] font-mono text-gray-400 uppercase">{label}</span>
      <p className={`text-sm font-medium ${highlight ? 'text-accent-red' : 'text-gray-700'}`}>{value}</p>
    </div>
  )
}
