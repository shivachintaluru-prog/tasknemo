import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { ScoreDistribution } from './ScoreDistribution'
import { SourceBreakdown } from './SourceBreakdown'
import { ResponseTimes } from './ResponseTimes'
import { SyncTimeline } from './SyncTimeline'

export function AnalyticsPage() {
  const [overview, setOverview] = useState<any>(null)
  const [responseTimes, setResponseTimes] = useState<any>(null)
  const [syncLog, setSyncLog] = useState<any>(null)
  const [quality, setQuality] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [ov, rt, sl, q] = await Promise.all([
          api.getAnalyticsOverview(),
          api.getResponseTimes(),
          api.getSyncLog(),
          api.getQuality(),
        ])
        setOverview(ov)
        setResponseTimes(rt)
        setSyncLog(sl)
        setQuality(q)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="text-sm text-gray-400 font-mono">Loading analytics...</span>
      </div>
    )
  }

  const totals = overview?.totals || {}

  return (
    <div className="space-y-6">
      {/* Big numbers row */}
      <div className="flex items-center justify-between py-3">
        <BigStat label="Focus" value={overview?.state_counts?.open || 0} color="text-accent-red" />
        <BigStat label="Open" value={totals.active || 0} color="text-purple" />
        <BigStat label="All Time" value={totals.all || 0} color="text-gray-700" />
        <BigStat label="Closed" value={totals.closed || 0} color="text-accent-green" />
        <BigStat label="Close Rate" value={`${totals.close_rate || 0}%`} color="text-accent-green" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-4">
          <h3 className="text-sm font-bold text-gray-600 mb-3">Score Distribution</h3>
          <ScoreDistribution data={overview?.score_distribution || []} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-4">
          <h3 className="text-sm font-bold text-gray-600 mb-3">Tasks by Source</h3>
          <SourceBreakdown data={overview?.source_counts || {}} />
        </div>
      </div>

      {/* Response Times */}
      <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-4">
        <h3 className="text-sm font-bold text-gray-600 mb-3">Response Times</h3>
        <ResponseTimes data={responseTimes?.response_times || []} />
      </div>

      {/* Quality Report */}
      {quality && (
        <div className="bg-white rounded-xl border-2 border-accent-orange/30 shadow-card p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-accent-orange/10 flex items-center justify-center">
              <span className="text-base">{'\uD83D\uDCCA'}</span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-700">Quality Report</h3>
              <p className="text-xs text-gray-400">Task extraction confidence analysis</p>
            </div>
            <div className="ml-auto text-right">
              <span className={`text-2xl font-black ${quality.avg_confidence >= 0.6 ? 'text-accent-green' : quality.avg_confidence >= 0.4 ? 'text-accent-orange' : 'text-accent-red'}`}>
                {Math.round(quality.avg_confidence * 100)}%
              </span>
              <p className="text-[10px] font-mono text-gray-400">AVG CONFIDENCE</p>
            </div>
          </div>
          {quality.low_confidence_tasks.length > 0 ? (
            <>
              <p className="text-xs text-gray-500 mb-2">
                {quality.low_confidence_tasks.length} tasks below 50% confidence — may need manual review:
              </p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {quality.low_confidence_tasks.slice(0, 15).map((t: any) => (
                  <div key={t.id} className="flex items-center gap-2 text-sm py-1 border-b border-gray-50 last:border-0">
                    <span className="font-mono text-xs text-gray-400 w-16 shrink-0">{t.id}</span>
                    <span className="flex-1 truncate text-gray-600">{t.title}</span>
                    <span className={`text-xs font-mono font-bold shrink-0 ${t.confidence < 0.3 ? 'text-accent-red' : 'text-accent-orange'}`}>
                      {Math.round(t.confidence * 100)}%
                    </span>
                    <span className="text-[10px] text-gray-400 shrink-0 w-24 text-right">{t.missing.join(', ')}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-accent-green font-medium">All tasks have good confidence scores.</p>
          )}
        </div>
      )}

      {/* Sync Activity */}
      <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-4">
        <h3 className="text-sm font-bold text-gray-600 mb-3">Sync Activity</h3>
        <SyncTimeline runs={syncLog?.runs || []} />
      </div>
    </div>
  )
}

function BigStat({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className={`text-[28px] font-black tabular-nums ${color}`}>{value}</span>
      <span className="text-[10px] font-mono font-medium text-gray-400 tracking-wider uppercase">{label}</span>
    </div>
  )
}
