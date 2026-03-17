import { useTaskStore } from '../../store/taskStore'

export function StatsBar() {
  const stats = useTaskStore((s) => s.dashboard?.stats)
  if (!stats) return null

  const items = [
    { label: 'FOCUS', value: stats.focus_count, color: 'text-accent-red' },
    { label: 'DUE SOON', value: stats.due_soon_count, color: 'text-accent-orange' },
    { label: 'OPEN', value: stats.open_count, color: 'text-purple' },
    { label: 'NUDGE', value: stats.nudge_count, color: 'text-accent-orange' },
    { label: 'STALE', value: stats.stale_count, color: 'text-gray-400' },
  ]

  return (
    <div className="flex items-center justify-between py-4 px-2">
      {items.map((item) => (
        <div key={item.label} className="flex flex-col items-center gap-0.5">
          <span className={`text-3xl font-black tabular-nums ${item.color}`}>
            {item.value}
          </span>
          <span className="text-[10px] font-mono font-medium text-gray-400 tracking-wider uppercase">
            {item.label}
          </span>
        </div>
      ))}
    </div>
  )
}
