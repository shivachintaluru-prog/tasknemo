interface Entry {
  sender: string
  avg_hours: number
  count: number
}

export function ResponseTimes({ data }: { data: Entry[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-gray-400 italic">No response time data yet.</p>
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-[10px] font-mono text-gray-400 uppercase">
          <th className="text-left pb-2">Sender</th>
          <th className="text-right pb-2">Avg Hours</th>
          <th className="text-right pb-2">Count</th>
        </tr>
      </thead>
      <tbody>
        {data.slice(0, 15).map((entry) => (
          <tr key={entry.sender} className="border-t border-gray-50">
            <td className="py-1.5 text-gray-700 capitalize">{entry.sender}</td>
            <td className="py-1.5 text-right font-mono text-gray-500">{entry.avg_hours}h</td>
            <td className="py-1.5 text-right font-mono text-gray-400">{entry.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
