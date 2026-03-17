interface Stakeholder {
  role: string
  weight: number
  title?: string
}

interface Props {
  stakeholders: Record<string, Stakeholder>
  onSave: (stakeholders: Record<string, Stakeholder>) => void
  saving: boolean
}

export function StakeholderTable({ stakeholders, onSave, saving }: Props) {
  const entries = Object.entries(stakeholders)
    .sort(([, a], [, b]) => b.weight - a.weight)

  if (entries.length === 0) {
    return <p className="text-sm text-gray-400 italic">No stakeholders configured.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-mono text-gray-400 uppercase">
            <th className="text-left pb-2">Name</th>
            <th className="text-left pb-2">Role</th>
            <th className="text-left pb-2">Title</th>
            <th className="text-right pb-2">Weight</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, s]) => (
            <tr key={name} className="border-t border-gray-50">
              <td className="py-2 font-medium text-gray-700 capitalize">{name}</td>
              <td className="py-2">
                <span className={`
                  px-1.5 py-0.5 rounded text-[10px] font-bold
                  ${s.role === 'manager' ? 'bg-purple/10 text-purple' :
                    s.role === 'skip' ? 'bg-purple/20 text-purple-dark' :
                    s.role === 'partner' ? 'bg-accent-green/10 text-accent-green' :
                    'bg-gray-100 text-gray-500'}
                `}>
                  {s.role}
                </span>
              </td>
              <td className="py-2 text-gray-500 text-xs">{s.title || ''}</td>
              <td className="py-2 text-right">
                <span className={`
                  inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold
                  ${s.weight >= 7 ? 'bg-purple text-white' :
                    s.weight >= 4 ? 'bg-purple/20 text-purple' :
                    'bg-gray-100 text-gray-500'}
                `}>
                  {s.weight}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
