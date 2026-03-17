import type { TaskGroup as TG } from '../../types/task'
import { TaskCard } from './TaskCard'

interface Props {
  group: TG
}

export function TaskGroup({ group }: Props) {
  const sourceIcons: Record<string, string> = {
    meeting: '\uD83D\uDCF9',
    chat: '\uD83D\uDCAC',
    direct: '\uD83D\uDC64',
  }

  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 mb-1.5 pl-1">
        <span className="text-xs">{sourceIcons[group.source_type] || '\uD83D\uDCCB'}</span>
        <span className="font-mono text-xs font-medium text-gray-500">
          {group.title}
        </span>
        <span className="text-[10px] text-gray-400">{group.tasks.length} tasks</span>
        {group.source_link && (
          <a
            href={group.source_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-purple hover:underline ml-auto"
          >
            Open
          </a>
        )}
      </div>
      <div className="space-y-2 pl-3 border-l-2 border-cream-dark">
        {group.tasks.map((t) => (
          <TaskCard key={t.id} task={t} section="open" />
        ))}
      </div>
    </div>
  )
}
