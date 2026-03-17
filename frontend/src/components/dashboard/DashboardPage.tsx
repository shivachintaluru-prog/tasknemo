import { useTaskStore } from '../../store/taskStore'
import { StatsBar } from '../layout/StatsBar'
import { QuickAdd } from './QuickAdd'
import { SectionBlock } from './SectionBlock'
import { TaskGroup } from './TaskGroup'
import { TaskCard } from './TaskCard'
import type { Task } from '../../types/task'

export function DashboardPage() {
  const dashboard = useTaskStore((s) => s.dashboard)
  const searchQuery = useTaskStore((s) => s.searchQuery)

  if (!dashboard) return null

  const { sections } = dashboard

  const filterTasks = (tasks: Task[]) => {
    if (!searchQuery) return tasks
    const q = searchQuery.toLowerCase()
    return tasks.filter(
      (t) =>
        t.title?.toLowerCase().includes(q) ||
        t.sender?.toLowerCase().includes(q) ||
        t.id?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q)
    )
  }

  return (
    <div className="space-y-2">
      <StatsBar />
      <QuickAdd />

      {/* Pinned */}
      {sections.pinned.length > 0 && (
        <SectionBlock
          title="Pinned"
          icon="pin"
          count={sections.pinned.length}
          accentColor="purple"
        >
          {filterTasks(sections.pinned).map((t) => (
            <TaskCard key={t.id} task={t} section="pinned" />
          ))}
        </SectionBlock>
      )}

      {/* Focus Now */}
      <SectionBlock
        title="Focus Now"
        icon="fire"
        count={sections.focus.length}
        accentColor="red"
      >
        {filterTasks(sections.focus).map((t) => (
          <TaskCard key={t.id} task={t} section="focus" />
        ))}
      </SectionBlock>

      {/* Due Soon */}
      {sections.due_soon.length > 0 && (
        <SectionBlock
          title="Due Soon"
          icon="clock"
          count={sections.due_soon.length}
          accentColor="orange"
        >
          {filterTasks(sections.due_soon).map((t) => (
            <TaskCard key={t.id} task={t} section="due_soon" />
          ))}
        </SectionBlock>
      )}

      {/* Open (grouped) */}
      <SectionBlock
        title="Open"
        icon="inbox"
        count={
          sections.open.groups.reduce((n, g) => n + g.tasks.length, 0) +
          sections.open.ungrouped.length
        }
        accentColor="purple"
      >
        {sections.open.groups.map((group) => {
          const filtered = filterTasks(group.tasks)
          if (filtered.length === 0) return null
          return <TaskGroup key={group.key} group={{ ...group, tasks: filtered }} />
        })}
        {filterTasks(sections.open.ungrouped).map((t) => (
          <TaskCard key={t.id} task={t} section="open" />
        ))}
      </SectionBlock>

      {/* Stale */}
      {sections.stale.length > 0 && (
        <SectionBlock
          title="Stale -- Close or Chase"
          icon="eye"
          count={sections.stale.length}
          accentColor="gray"
        >
          {filterTasks(sections.stale).map((t) => (
            <TaskCard key={t.id} task={t} section="stale" />
          ))}
        </SectionBlock>
      )}

      {/* Nudge Needed */}
      {sections.nudge.length > 0 && (
        <SectionBlock
          title="Nudge Needed"
          icon="megaphone"
          count={sections.nudge.length}
          accentColor="orange"
        >
          {filterTasks(sections.nudge).map((t) => (
            <TaskCard key={t.id} task={t} section="nudge" />
          ))}
        </SectionBlock>
      )}

      {/* Waiting for Reply */}
      {sections.waiting_outbound.length > 0 && (
        <SectionBlock
          title="Waiting for Reply"
          icon="hourglass"
          count={sections.waiting_outbound.length}
          accentColor="green"
        >
          {filterTasks(sections.waiting_outbound).map((t) => (
            <TaskCard key={t.id} task={t} section="waiting" />
          ))}
        </SectionBlock>
      )}

      {/* Closed by Me */}
      {sections.closed_by_me.length > 0 && (
        <SectionBlock
          title="Closed by Me"
          icon="check"
          count={sections.closed_by_me.length}
          accentColor="green"
        >
          {filterTasks(sections.closed_by_me).map((t) => (
            <TaskCard key={t.id} task={t} section="closed" />
          ))}
        </SectionBlock>
      )}

      {/* Recently Closed */}
      {sections.recently_closed.length > 0 && (
        <SectionBlock
          title="Recently Closed"
          icon="check"
          count={sections.recently_closed.length}
          accentColor="green"
        >
          {filterTasks(sections.recently_closed).map((t) => (
            <TaskCard key={t.id} task={t} section="closed" />
          ))}
        </SectionBlock>
      )}
    </div>
  )
}
