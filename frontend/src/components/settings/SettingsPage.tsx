import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { StakeholderTable } from './StakeholderTable'
import { MetricTiles } from './MetricTiles'

export function SettingsPage() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const data = await api.getConfig()
        setConfig(data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSave = async (updates: Record<string, any>) => {
    setSaving(true)
    try {
      await api.updateConfig(updates)
      const refreshed = await api.getConfig()
      setConfig(refreshed)
    } finally {
      setSaving(false)
    }
  }

  if (loading || !config) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="text-sm text-gray-400 font-mono">Loading settings...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stakeholders */}
      <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-5">
        <h3 className="text-sm font-bold text-gray-600 mb-3">Stakeholders</h3>
        <StakeholderTable
          stakeholders={config.stakeholders || {}}
          onSave={(stakeholders) => handleSave({ stakeholders })}
          saving={saving}
        />
      </div>

      {/* Auto-close thresholds */}
      <MetricTiles
        title="Auto-Close Thresholds"
        items={[
          {
            label: 'Likely Done',
            value: config.auto_close_likely_done_days || 3,
            unit: 'days',
            color: 'orange',
          },
          {
            label: 'Stale',
            value: config.auto_close_stale_days || 7,
            unit: 'days',
            color: 'orange',
          },
          {
            label: 'Open',
            value: config.auto_close_open_days || 10,
            unit: 'days',
            color: 'orange',
          },
        ]}
      />

      {/* Scoring boosts */}
      <MetricTiles
        title="Scoring Boosts"
        items={[
          {
            label: 'Calendar',
            value: config.scoring?.calendar_boost || 5,
            unit: 'pts',
            color: 'purple',
          },
          {
            label: 'Manual',
            value: config.scoring?.manual_boost || 15,
            unit: 'pts',
            color: 'purple',
          },
          {
            label: 'Pin',
            value: 20,
            unit: 'pts',
            color: 'purple',
          },
        ]}
      />

      {/* Sources */}
      <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-5">
        <h3 className="text-sm font-bold text-gray-600 mb-3">Enabled Sources</h3>
        <div className="flex flex-wrap gap-2">
          {(config.sources_enabled || []).map((src: string) => (
            <span key={src} className="px-3 py-1 rounded-full text-xs font-semibold bg-purple/10 text-purple capitalize">
              {src}
            </span>
          ))}
        </div>
      </div>

      {/* Keywords */}
      <div className="bg-white rounded-xl border border-gray-200/80 shadow-card p-5">
        <h3 className="text-sm font-bold text-gray-600 mb-3">Urgency Keywords</h3>
        <div className="flex flex-wrap gap-1.5">
          {(config.urgency_keywords || []).map((kw: string) => (
            <span key={kw} className="px-2 py-0.5 rounded text-[11px] font-medium bg-accent-red/10 text-accent-red">
              {kw}
            </span>
          ))}
          {(config.urgency_keywords || []).length === 0 && (
            <span className="text-sm text-gray-400 italic">No urgency keywords configured.</span>
          )}
        </div>
      </div>
    </div>
  )
}
