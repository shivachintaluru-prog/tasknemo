interface Run {
  timestamp: string
  new_tasks?: number
  transitions?: number
  merged?: number
  skipped?: number
  sources_queried?: string[]
  error?: string
}

export function SyncTimeline({ runs }: { runs: Run[] }) {
  if (runs.length === 0) {
    return <p className="text-sm text-gray-400 italic">No sync runs recorded.</p>
  }

  return (
    <div className="space-y-2 max-h-80 overflow-y-auto">
      {runs.slice(0, 20).map((run, i) => {
        const ts = new Date(run.timestamp)
        const dateStr = ts.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        const timeStr = ts.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
        const isFullSync = !!run.sources_queried
        const hasError = !!run.error

        return (
          <div key={i} className="flex items-start gap-3 text-sm">
            <span className="font-mono text-[11px] text-gray-400 shrink-0 w-24">
              {dateStr} {timeStr}
            </span>
            <div className="flex flex-wrap gap-1.5">
              <Badge color={isFullSync ? '#6C5CE7' : '#A0A0A0'}>
                {isFullSync ? 'Full' : 'Refresh'}
              </Badge>
              {(run.new_tasks || 0) > 0 && (
                <Badge color="#38A169">+{run.new_tasks} new</Badge>
              )}
              {(run.transitions || 0) > 0 && (
                <Badge color="#6C5CE7">{run.transitions} trans</Badge>
              )}
              {(run.merged || 0) > 0 && (
                <Badge color="#DD8800">{run.merged} merged</Badge>
              )}
              {hasError && <Badge color="#E74C4C">error</Badge>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Badge({ children, color }: { children: React.ReactNode; color: string }) {
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold text-white"
      style={{ backgroundColor: color }}
    >
      {children}
    </span>
  )
}
