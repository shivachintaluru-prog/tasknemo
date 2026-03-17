import { useTaskStore } from '../../store/taskStore'

interface Props {
  onRefresh: () => void
}

export function Header({ onRefresh }: Props) {
  const { searchQuery, setSearch, dashboard, loading } = useTaskStore()
  const syncHealth = dashboard?.stats?.sync_health || ''
  const lastSynced = dashboard?.stats?.last_synced || ''
  const isHealthy = syncHealth.includes('\u2713')

  return (
    <header className="sticky top-0 z-40 bg-cream/90 backdrop-blur-md border-b border-cream-dark/60">
      <div className="max-w-dashboard mx-auto px-4 py-3 flex items-center gap-4">
        {/* Logo */}
        <div className="flex items-center gap-1.5 shrink-0">
          <div className="w-7 h-7 bg-purple rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-xs tracking-tight">N</span>
          </div>
          <h1 className="text-lg font-extrabold tracking-tight">
            Task<span className="text-purple">Nemo</span>
          </h1>
        </div>

        {/* Search */}
        <div className="flex-1 max-w-xs relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-white border border-cream-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-purple/30 focus:border-purple/40 placeholder:text-gray-400 transition-all"
          />
        </div>

        {/* Sync status */}
        <div className="flex items-center gap-2 shrink-0 text-xs text-gray-500">
          <div className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-accent-green' : 'bg-accent-orange'} ${loading ? 'animate-pulse' : ''}`} />
          <span className="font-mono hidden sm:inline">{lastSynced}</span>
          <button
            onClick={onRefresh}
            className="p-1.5 rounded-md hover:bg-cream-dark/60 transition-colors"
            title="Refresh dashboard"
          >
            <svg className={`w-3.5 h-3.5 text-gray-500 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}
