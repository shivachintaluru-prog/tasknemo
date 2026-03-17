import { useTaskStore } from '../../store/taskStore'

const TABS = [
  { key: 'dashboard' as const, label: 'Dashboard' },
  { key: 'analytics' as const, label: 'Analytics' },
  { key: 'settings' as const, label: 'Settings' },
]

export function TabNav() {
  const { activeTab, setActiveTab } = useTaskStore()

  return (
    <div className="flex gap-1 border-b border-cream-dark/60 mb-4">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          onClick={() => setActiveTab(tab.key)}
          className={`
            px-4 py-2.5 text-sm font-semibold transition-all relative
            ${activeTab === tab.key
              ? 'text-purple'
              : 'text-gray-400 hover:text-gray-600'
            }
          `}
        >
          {tab.label}
          {activeTab === tab.key && (
            <div className="absolute bottom-0 left-2 right-2 h-[2.5px] bg-purple rounded-full" />
          )}
        </button>
      ))}
    </div>
  )
}
