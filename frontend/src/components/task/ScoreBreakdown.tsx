import type { Task } from '../../types/task'

const BREAKDOWN_LABELS: Record<string, { label: string; max: number; color: string }> = {
  stakeholder: { label: 'Stakeholder', max: 40, color: '#6C5CE7' },
  urgency: { label: 'Urgency', max: 30, color: '#E74C4C' },
  age: { label: 'Age', max: 20, color: '#DD8800' },
  thread: { label: 'Thread', max: 10, color: '#38A169' },
  pin: { label: 'Pin Boost', max: 20, color: '#6C5CE7' },
  manual_boost: { label: 'Manual', max: 15, color: '#A29BFE' },
  escalation: { label: 'Escalation', max: 15, color: '#E74C4C' },
  response_time: { label: 'Response', max: 10, color: '#DD8800' },
  user_priority_boost: { label: 'Priority', max: 20, color: '#6C5CE7' },
}

interface Props {
  task: Task
}

export function ScoreBreakdown({ task }: Props) {
  const breakdown = task.score_breakdown || {}
  const entries = Object.entries(breakdown).filter(([, v]) => v > 0)

  if (entries.length === 0) return null

  return (
    <div>
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
        Score Breakdown
        <span className="ml-2 text-gray-600 font-black text-sm normal-case">{task.score}</span>
      </h3>
      <div className="space-y-1.5">
        {entries.map(([key, value]) => {
          const info = BREAKDOWN_LABELS[key] || { label: key, max: 20, color: '#A0A0A0' }
          const pct = Math.min((value / info.max) * 100, 100)
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[11px] text-gray-500 w-20 text-right shrink-0">{info.label}</span>
              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: info.color }}
                />
              </div>
              <span className="text-[11px] font-mono text-gray-500 w-6 text-right">{value}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
