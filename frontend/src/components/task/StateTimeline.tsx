import type { Task } from '../../types/task'

const STATE_COLORS: Record<string, string> = {
  open: '#6C5CE7',
  waiting: '#DD8800',
  needs_followup: '#DD8800',
  likely_done: '#38A169',
  closed: '#38A169',
}

interface Props {
  task: Task
}

export function StateTimeline({ task }: Props) {
  const history = task.state_history || []
  if (history.length === 0) return null

  return (
    <div>
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">State History</h3>
      <div className="relative pl-4">
        {/* Vertical line */}
        <div className="absolute left-[5px] top-1 bottom-1 w-[2px] bg-gray-200" />

        {history.map((entry, i) => {
          const color = STATE_COLORS[entry.state] || '#A0A0A0'
          const date = new Date(entry.date)
          const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
          return (
            <div key={i} className="relative flex items-start gap-3 pb-3 last:pb-0">
              <div
                className="absolute left-[-12px] top-1 w-[10px] h-[10px] rounded-full border-2 bg-white z-10"
                style={{ borderColor: color }}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-bold text-white"
                    style={{ backgroundColor: color }}
                  >
                    {entry.state}
                  </span>
                  <span className="text-[10px] font-mono text-gray-400">{dateStr} {timeStr}</span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5 truncate">{entry.reason}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
