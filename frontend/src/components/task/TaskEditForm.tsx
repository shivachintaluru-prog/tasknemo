import { useState } from 'react'
import type { Task } from '../../types/task'
import { api } from '../../api/client'
import { useDashboard } from '../../hooks/useDashboard'

interface Props {
  task: Task
}

export function TaskEditForm({ task }: Props) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description || '')
  const [dueHint, setDueHint] = useState(task.due_hint || '')
  const [nextStep, setNextStep] = useState(task.next_step || '')
  const [saving, setSaving] = useState(false)
  const { refresh } = useDashboard()

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateTask(task.id, {
        title: title !== task.title ? title : undefined,
        description: description !== (task.description || '') ? description : undefined,
        due_hint: dueHint !== (task.due_hint || '') ? dueHint : undefined,
        next_step: nextStep !== (task.next_step || '') ? nextStep : undefined,
      })
      refresh()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3">
      <Field label="Title" value={title} onChange={setTitle} />
      <Field label="Description" value={description} onChange={setDescription} multiline />
      <Field label="Due Hint" value={dueHint} onChange={setDueHint} placeholder="eod friday, tomorrow, etc." />
      <Field label="Next Step" value={nextStep} onChange={setNextStep} />
      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full py-2 bg-purple text-white text-sm font-bold rounded-lg hover:bg-purple-dark disabled:opacity-40 transition-colors"
      >
        {saving ? 'Saving...' : 'Save Changes'}
      </button>
    </div>
  )
}

function Field({
  label, value, onChange, multiline, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; multiline?: boolean; placeholder?: string
}) {
  const cls = "w-full px-2 py-1.5 text-sm bg-gray-50 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-purple/30"
  return (
    <div>
      <label className="text-[10px] font-mono text-gray-400 uppercase">{label}</label>
      {multiline ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={2} className={cls} placeholder={placeholder} />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} className={cls} placeholder={placeholder} />
      )}
    </div>
  )
}
