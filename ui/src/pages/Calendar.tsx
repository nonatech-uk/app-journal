import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCalendar } from '../api/meta'

const MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function Calendar() {
  const { data: months, isLoading } = useQuery({ queryKey: ['calendar'], queryFn: fetchCalendar })

  if (isLoading) return <div className="text-text-secondary">Loading...</div>

  // Group by year
  const byYear: Record<number, typeof months> = {}
  months?.forEach((m) => {
    if (!byYear[m.year]) byYear[m.year] = []
    byYear[m.year]!.push(m)
  })

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Calendar</h2>
      <div className="space-y-6">
        {Object.entries(byYear)
          .sort(([a], [b]) => Number(b) - Number(a))
          .map(([year, yearMonths]) => (
            <div key={year}>
              <h3 className="text-lg font-semibold mb-2">{year}</h3>
              <div className="grid grid-cols-4 gap-2">
                {yearMonths!
                  .sort((a, b) => b.month - a.month)
                  .map((m) => (
                    <Link
                      key={`${m.year}-${m.month}`}
                      to={`/timeline?year=${m.year}&month=${m.month}`}
                      className="bg-bg-card border border-border rounded-lg p-3 hover:border-accent/30 transition-colors"
                    >
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm font-medium">{MONTH_NAMES[m.month]}</span>
                        <span className="text-xs text-text-secondary">{m.entry_count}</span>
                      </div>
                      <div className="flex flex-wrap gap-0.5">
                        {m.days.map((d) => (
                          <span
                            key={d}
                            className="w-4 h-4 flex items-center justify-center text-[9px] bg-accent/10 text-accent rounded"
                          >
                            {d}
                          </span>
                        ))}
                      </div>
                    </Link>
                  ))}
              </div>
            </div>
          ))}
      </div>
    </div>
  )
}
