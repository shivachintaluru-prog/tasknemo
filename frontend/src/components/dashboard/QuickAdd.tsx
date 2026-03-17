import { useState } from 'react'
import { api } from '../../api/client'
import { useDashboard } from '../../hooks/useDashboard'

export function QuickAdd() {
  const [input, setInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { refresh } = useDashboard()

  const handleSubmit = async () => {
    const raw = input.trim()
    if (!raw || submitting) return

    // Parse inline flags: --sender X --due Y --priority Z
    let title = raw
    let sender: string | undefined
    let dueHint: string | undefined
    let priority: string | undefined

    const flagRegex = /--(\w+)\s+([^-]+?)(?=\s+--|$)/g
    let match
    while ((match = flagRegex.exec(raw)) !== null) {
      const [, flag, value] = match
      if (flag === 'sender') sender = value.trim()
      else if (flag === 'due') dueHint = value.trim()
      else if (flag === 'priority') priority = value.trim()
    }
    title = title.replace(flagRegex, '').trim()

    setSubmitting(true)
    try {
      await api.createTask({
        title,
        sender: sender || 'me',
        due_hint: dueHint || null,
        priority: priority || null,
      })
      setInput('')
      refresh()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex gap-2 mb-5">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        placeholder="Add task... (--sender Name --due eod --priority high)"
        className="flex-1 px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg
          focus:outline-none focus:ring-2 focus:ring-purple/30 focus:border-purple/40
          placeholder:text-gray-400 transition-all font-mono text-[13px]"
      />
      <button
        onClick={handleSubmit}
        disabled={!input.trim() || submitting}
        className="px-4 py-2 bg-purple text-white text-sm font-bold rounded-lg
          hover:bg-purple-dark disabled:opacity-40 disabled:cursor-not-allowed
          transition-colors shrink-0"
      >
        {submitting ? '...' : 'Add Task'}
      </button>
    </div>
  )
}
