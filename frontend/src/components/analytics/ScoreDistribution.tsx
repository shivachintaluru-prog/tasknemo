interface DataPoint {
  range: string
  count: number
}

function barColor(range: string) {
  const start = parseInt(range)
  if (start >= 70) return '#38A169'
  if (start >= 40) return '#DD8800'
  return '#6C5CE7'
}

export function ScoreDistribution({ data }: { data: DataPoint[] }) {
  const maxCount = Math.max(...data.map((d) => d.count), 1)

  return (
    <div className="space-y-1.5">
      {data.map((d) => (
        <div key={d.range} className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-gray-400 w-10 text-right shrink-0">{d.range}</span>
          <div className="flex-1 h-4 bg-gray-50 rounded overflow-hidden">
            <div
              className="h-full rounded transition-all"
              style={{
                width: `${(d.count / maxCount) * 100}%`,
                backgroundColor: barColor(d.range),
                minWidth: d.count > 0 ? '4px' : 0,
              }}
            />
          </div>
          <span className="text-[11px] font-mono text-gray-500 w-6 text-right">{d.count}</span>
        </div>
      ))}
    </div>
  )
}
