import { ReactNode, useState } from 'react'

const ICONS: Record<string, string> = {
  fire: '\uD83D\uDD25',
  clock: '\u23F0',
  inbox: '\uD83D\uDCCB',
  eye: '\uD83D\uDD0D',
  megaphone: '\uD83D\uDCE3',
  hourglass: '\u23F3',
  check: '\u2705',
  pin: '\uD83D\uDCCC',
}

const ACCENT_COLORS: Record<string, string> = {
  red: 'bg-accent-red',
  orange: 'bg-accent-orange',
  purple: 'bg-purple',
  green: 'bg-accent-green',
  gray: 'bg-accent-gray',
}

interface Props {
  title: string
  icon: string
  count: number
  accentColor: string
  children: ReactNode
}

export function SectionBlock({ title, icon, count, accentColor, children }: Props) {
  const [collapsed, setCollapsed] = useState(false)
  const hasChildren = Array.isArray(children) ? children.some(Boolean) : !!children

  return (
    <section className="mb-5">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 mb-2.5 group cursor-pointer w-full text-left"
      >
        <span className="text-base">{ICONS[icon] || ''}</span>
        <h2 className="text-[15px] font-extrabold text-gray-700 tracking-tight">
          {title}
        </h2>
        <span className={`
          inline-flex items-center justify-center min-w-[20px] h-5 px-1.5
          text-[11px] font-bold text-white rounded-full
          ${ACCENT_COLORS[accentColor] || 'bg-gray-400'}
        `}>
          {count}
        </span>
        <svg
          className={`w-3.5 h-3.5 text-gray-400 transition-transform ml-auto ${collapsed ? '-rotate-90' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {!collapsed && (
        <div className="space-y-2 animate-fade-in">
          {hasChildren ? children : (
            <p className="text-sm text-gray-400 italic pl-1 py-2">No tasks in this section.</p>
          )}
        </div>
      )}
    </section>
  )
}
