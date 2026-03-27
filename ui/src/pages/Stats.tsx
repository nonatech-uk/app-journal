import { useQuery } from '@tanstack/react-query'
import { fetchStats } from '../api/meta'

export default function Stats() {
  const { data: stats, isLoading } = useQuery({ queryKey: ['stats'], queryFn: fetchStats })

  if (isLoading) return <div className="text-text-secondary">Loading...</div>
  if (!stats) return null

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Stats</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Entries', value: stats.total_entries },
          { label: 'Photos', value: stats.total_photos },
          { label: 'Videos', value: stats.total_videos },
          { label: 'Starred', value: stats.starred_entries },
          { label: 'Locations', value: stats.entries_with_location },
          { label: 'Weather', value: stats.entries_with_weather },
          { label: 'Music', value: stats.entries_with_music },
          { label: 'Tags', value: stats.total_tags },
        ].map((s) => (
          <div key={s.label} className="bg-bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold">{s.value.toLocaleString()}</div>
            <div className="text-xs text-text-secondary">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Date range */}
      {stats.date_range_start && stats.date_range_end && (
        <div className="text-sm text-text-secondary mb-4">
          {new Date(stats.date_range_start).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
          {' — '}
          {new Date(stats.date_range_end).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
        </div>
      )}

      {/* Entries by year */}
      <div className="bg-bg-card border border-border rounded-lg p-4 mb-6">
        <h3 className="text-sm font-medium mb-3">Entries by Year</h3>
        <div className="space-y-1">
          {Object.entries(stats.entries_by_year)
            .sort(([a], [b]) => Number(b) - Number(a))
            .map(([year, count]) => {
              const max = Math.max(...Object.values(stats.entries_by_year))
              return (
                <div key={year} className="flex items-center gap-2">
                  <span className="text-xs w-10 text-text-secondary">{year}</span>
                  <div className="flex-1 h-4 bg-bg-hover rounded overflow-hidden">
                    <div
                      className="h-full bg-accent/30 rounded"
                      style={{ width: `${(count / max) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-secondary w-10 text-right">{count}</span>
                </div>
              )
            })}
        </div>
      </div>

      {/* Top tags */}
      <div className="bg-bg-card border border-border rounded-lg p-4 mb-6">
        <h3 className="text-sm font-medium mb-3">Top Tags</h3>
        <div className="flex flex-wrap gap-2">
          {stats.top_tags.map((t) => (
            <span key={t.id} className="text-xs px-2 py-1 rounded-full bg-accent/10 text-accent">
              {t.name} ({t.entry_count})
            </span>
          ))}
        </div>
      </div>

      {/* Top locations */}
      <div className="bg-bg-card border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium mb-3">Top Locations</h3>
        <div className="space-y-1">
          {stats.top_locations.map((l, i) => (
            <div key={i} className="flex justify-between text-sm">
              <span>{l.locality}, {l.country}</span>
              <span className="text-text-secondary">{l.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
