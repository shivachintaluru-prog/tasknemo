import { useState } from 'react'
import type { Task } from '../../types/task'
import { useTaskStore } from '../../store/taskStore'
import { api } from '../../api/client'
import { useDashboard } from '../../hooks/useDashboard'

const SECTION_ACCENT: Record<string, string> = {
  pinned: '#6C5CE7',
  focus: '#E74C4C',
  due_soon: '#DD8800',
  open: '#6C5CE7',
  stale: '#A0A0A0',
  nudge: '#DD8800',
  waiting: '#38A169',
  closed: '#38A169',
}

const SCORE_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: 'bg-accent-red/10', text: 'text-accent-red' },
  medium: { bg: 'bg-accent-orange/10', text: 'text-accent-orange' },
  low: { bg: 'bg-purple/10', text: 'text-purple' },
  minimal: { bg: 'bg-gray-100', text: 'text-gray-400' },
}

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-accent-red text-white',
  medium: 'bg-accent-orange text-white',
  low: 'bg-gray-200 text-gray-600',
}

function scoreCategory(score: number) {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  if (score >= 20) return 'low'
  return 'minimal'
}

function getPriorityLabel(task: Task): string | null {
  const p = task.user_priority
  if (p === undefined || p === null || p === 0) return null
  if (p >= 20) return 'high'
  if (p >= 10) return 'medium'
  return 'low'
}

interface Props {
  task: Task
  section: string
}

export function TaskCard({ task, section }: Props) {
  const [closing, setClosing] = useState(false)
  const [acting, setActing] = useState(false)
  const [showPriority, setShowPriority] = useState(false)
  const selectTask = useTaskStore((s) => s.selectTask)
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId)
  const { refresh } = useDashboard()

  const isSelected = selectedTaskId === task.id
  const isClosed = task.state === 'closed'
  const accent = SECTION_ACCENT[section] || '#6C5CE7'
  const cat = scoreCategory(task.score)
  const scoreColor = SCORE_COLORS[cat]
  const priority = getPriorityLabel(task)

  const handleClose = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (acting || closing) return
    // Fire API immediately, show animation while it processes
    setClosing(true)
    setActing(true)
    try {
      await api.closeTask(task.id)
      // Keep closing=true — don't reset. Component will unmount
      // when refresh returns new dashboard data without this task.
      await refresh()
    } catch {
      // Only reset on failure so user can retry
      setClosing(false)
      setActing(false)
    }
  }

  const handlePin = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (acting) return
    setActing(true)
    try {
      if (task._is_pinned) {
        await api.unpinTask(task.id)
      } else {
        await api.pinTask(task.id)
      }
      refresh()
    } finally {
      setActing(false)
    }
  }

  const handleReopen = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (acting) return
    setActing(true)
    try {
      await api.reopenTask(task.id)
      refresh()
    } finally {
      setActing(false)
    }
  }

  const handlePriority = async (e: React.MouseEvent, level: string) => {
    e.stopPropagation()
    setShowPriority(false)
    const priorityMap: Record<string, number> = { high: 20, medium: 10, low: 0 }
    try {
      await api.updateTask(task.id, { user_priority: priorityMap[level] })
      refresh()
    } catch {}
  }

  return (
    <div
      onClick={() => selectTask(isSelected ? null : task.id)}
      className={`
        relative bg-white rounded-[10px] border border-gray-200/80
        cursor-pointer overflow-hidden group
        transition-all duration-200
        hover:shadow-card-hover hover:-translate-y-[2px]
        ${isSelected ? 'ring-2 ring-purple/40 shadow-card-selected' : 'shadow-card'}
        ${isClosed ? 'opacity-60' : ''}
        ${closing ? 'scale-[0.97] opacity-0 translate-x-4' : ''}
      `}
      style={{ transition: closing ? 'all 0.45s cubic-bezier(0.4, 0, 0.2, 1)' : undefined }}
    >
      {/* Left accent stripe */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[3.5px] rounded-l-[10px]"
        style={{ backgroundColor: closing ? '#38A169' : accent }}
      />

      {/* Closing overlay animation */}
      {closing && (
        <div className="absolute inset-0 bg-accent-green/5 z-10 flex items-center justify-center animate-fade-in">
          <div className="w-8 h-8 rounded-full bg-accent-green flex items-center justify-center animate-bounce">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>
      )}

      <div className="pl-4 pr-3 py-3">
        {/* Row 1: ID + Title + Score */}
        <div className="flex items-start gap-2 mb-1.5">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-[11px] text-gray-400 shrink-0">{task.id}</span>
              {task._is_pinned && (
                <span className="text-[10px]" title="Pinned">{'\uD83D\uDCCC'}</span>
              )}
              {priority && (
                <span className={`px-1 py-0 rounded text-[9px] font-bold uppercase ${PRIORITY_COLORS[priority]}`}>
                  {priority === 'high' ? 'P0' : priority === 'medium' ? 'P1' : 'P2'}
                </span>
              )}
            </div>
            <h3 className={`text-[15px] font-bold text-gray-800 leading-snug ${isClosed || closing ? 'line-through text-gray-400' : ''}`}>
              {task.title}
            </h3>
          </div>
          <span className={`
            shrink-0 px-2 py-0.5 rounded-full text-[11px] font-bold tabular-nums
            ${scoreColor.bg} ${scoreColor.text}
          `}>
            {task.score}
          </span>
        </div>

        {/* Row 2: Chips */}
        <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
          {task.sender && (
            <Chip>
              {task.direction === 'outbound' ? '\u2192' : '\u2190'} {task.sender}
            </Chip>
          )}
          {task._source_context && (
            <Chip><span className="text-gray-500">{task._source_context}</span></Chip>
          )}
          <Chip>{task._age}</Chip>
          {task.due_hint && (
            <Chip highlight={task._is_overdue}>
              {'\uD83D\uDCC5'} {task.due_hint}
            </Chip>
          )}
          <SourceChip source={task.source} link={task.teams_link || task.source_link} />
        </div>

        {/* Row 3: Next action */}
        {task._next_action && !isClosed && (
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple/10 text-purple">
              next
            </span>
            <span className="text-xs text-gray-600 truncate">{task._next_action}</span>
          </div>
        )}

        {/* Row 4: Links */}
        {task._links && task._links.length > 0 && !isClosed && (
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            {task._links.map((link, i) => (
              link.url ? (
                <a
                  key={i}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-purple/70 hover:text-purple hover:underline"
                >
                  {link.label}
                </a>
              ) : link.fallback ? (
                <span key={i} className="text-gray-400 italic text-[10px]">{link.fallback}</span>
              ) : null
            ))}
          </div>
        )}

        {/* Action bar — always visible, not hover-dependent */}
        {!closing && (
          <div className="flex items-center gap-1 mt-2 pt-2 border-t border-gray-100">
            {!isClosed ? (
              <>
                <ActionButton onClick={handlePin} title={task._is_pinned ? 'Unpin' : 'Pin'}>
                  {task._is_pinned ? '\uD83D\uDCCC Unpin' : 'Pin'}
                </ActionButton>
                <div className="relative">
                  <ActionButton
                    onClick={(e) => { e.stopPropagation(); setShowPriority(!showPriority) }}
                    title="Set priority"
                  >
                    Priority
                  </ActionButton>
                  {showPriority && (
                    <div className="absolute bottom-full left-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 overflow-hidden">
                      {['high', 'medium', 'low'].map((level) => (
                        <button
                          key={level}
                          onClick={(e) => handlePriority(e, level)}
                          className="block w-full px-3 py-1.5 text-left text-[11px] font-semibold hover:bg-gray-50 capitalize"
                        >
                          <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
                            level === 'high' ? 'bg-accent-red' : level === 'medium' ? 'bg-accent-orange' : 'bg-gray-300'
                          }`} />
                          {level}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="ml-auto">
                  <button
                    onClick={handleClose}
                    disabled={acting}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold
                      text-accent-green/80 hover:bg-accent-green/10 hover:text-accent-green
                      disabled:opacity-40 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                    Done
                  </button>
                </div>
              </>
            ) : (
              <ActionButton onClick={handleReopen} title="Reopen">
                Reopen
              </ActionButton>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function SourceChip({ source, link }: { source: string; link?: string }) {
  const SOURCE_ICONS: Record<string, string> = {
    teams: '\uD83D\uDCAC',
    email: '\u2709\uFE0F',
    calendar: '\uD83D\uDCC5',
    transcript: '\uD83C\uDFA4',
    manual: '\u270D\uFE0F',
    flagged_email: '\uD83D\uDEA9',
    sent_items: '\uD83D\uDCE4',
    outbound: '\u27A1\uFE0F',
    key_contacts: '\u2B50',
  }
  const icon = SOURCE_ICONS[source] || '\uD83D\uDCCB'

  if (link) {
    return (
      <a
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple/8 text-purple hover:bg-purple/15 transition-colors"
      >
        {icon} {source}
      </a>
    )
  }

  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500">
      {icon} {source}
    </span>
  )
}

function Chip({ children, highlight }: { children: React.ReactNode; highlight?: boolean }) {
  return (
    <span className={`
      inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium
      ${highlight ? 'bg-accent-red/10 text-accent-red font-semibold' : 'bg-gray-100 text-gray-500'}
    `}>
      {children}
    </span>
  )
}

function ActionButton({
  children, onClick, title, variant,
}: {
  children: React.ReactNode
  onClick: (e: React.MouseEvent) => void
  title: string
  variant?: 'danger'
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`
        px-2 py-1 rounded text-[11px] font-semibold transition-colors
        ${variant === 'danger'
          ? 'text-accent-red/70 hover:bg-accent-red/10 hover:text-accent-red'
          : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
        }
      `}
    >
      {children}
    </button>
  )
}
