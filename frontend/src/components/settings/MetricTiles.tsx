interface TileItem {
  label: string
  value: number
  unit: string
  color: 'orange' | 'purple'
}

interface Props {
  title: string
  items: TileItem[]
}

const TILE_COLORS = {
  orange: { bg: 'bg-accent-orange/10', text: 'text-accent-orange' },
  purple: { bg: 'bg-purple/10', text: 'text-purple' },
}

export function MetricTiles({ title, items }: Props) {
  return (
    <div>
      <h3 className="text-sm font-bold text-gray-600 mb-3">{title}</h3>
      <div className="grid grid-cols-3 gap-3">
        {items.map((item) => {
          const colors = TILE_COLORS[item.color]
          return (
            <div
              key={item.label}
              className="bg-white rounded-xl border border-gray-200/80 shadow-card p-4 text-center"
            >
              <span className={`text-2xl font-black tabular-nums ${colors.text}`}>
                {item.value}
              </span>
              <span className="text-xs text-gray-400 ml-1">{item.unit}</span>
              <p className="text-[11px] font-mono text-gray-400 mt-1">{item.label}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
