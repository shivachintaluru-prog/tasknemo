const SOURCE_COLORS: Record<string, string> = {
  teams: '#6C5CE7',
  email: '#E74C4C',
  calendar: '#DD8800',
  transcript: '#38A169',
  manual: '#A29BFE',
  flagged_email: '#E74C4C',
  planner: '#6C5CE7',
}

export function SourceBreakdown({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort(([, a], [, b]) => b - a)
  const total = entries.reduce((sum, [, v]) => sum + v, 0) || 1

  return (
    <div className="space-y-2.5">
      {entries.map(([source, count]) => {
        const pct = Math.round((count / total) * 100)
        const color = SOURCE_COLORS[source] || '#A0A0A0'
        return (
          <div key={source}>
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-xs font-medium text-gray-600 capitalize">{source.replace('_', ' ')}</span>
              <span className="text-[11px] font-mono text-gray-400">{count} ({pct}%)</span>
            </div>
            <div className="h-2.5 bg-gray-50 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, backgroundColor: color }}
              />
            </div>
          </div>
        )
      })}
      {entries.length === 0 && (
        <p className="text-sm text-gray-400 italic">No source data available.</p>
      )}
    </div>
  )
}
