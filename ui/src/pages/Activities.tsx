import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchActivities } from '../api/activities'

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatDuration(seconds: number | null) {
  if (!seconds) return ''
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatDistance(km: number | null) {
  if (km == null) return ''
  return km < 10 ? km.toFixed(1) : Math.round(km).toString()
}

function YearFilter({ years, selected, onChange }: {
  years: { year: number; count: number }[]
  selected: number | undefined
  onChange: (y: number | undefined) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5 mb-4">
      <button
        className={`px-2 py-1 text-xs rounded ${
          !selected ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
        }`}
        onClick={() => onChange(undefined)}
      >
        All
      </button>
      {years.map(y => (
        <button
          key={y.year}
          className={`px-2 py-1 text-xs rounded ${
            selected === y.year ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
          }`}
          onClick={() => onChange(y.year)}
        >
          {y.year} ({y.count})
        </button>
      ))}
    </div>
  )
}

function TypeFilter({ types, selected, onChange }: {
  types: { type: string; count: number }[]
  selected: string | undefined
  onChange: (t: string | undefined) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5 mb-4">
      <button
        className={`px-2 py-1 text-xs rounded ${
          !selected ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
        }`}
        onClick={() => onChange(undefined)}
      >
        All
      </button>
      {types.map(t => (
        <button
          key={t.type}
          className={`px-2 py-1 text-xs rounded ${
            selected === t.type ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
          }`}
          onClick={() => onChange(t.type)}
        >
          {t.type.charAt(0).toUpperCase() + t.type.slice(1)} ({t.count})
        </button>
      ))}
    </div>
  )
}

export default function Activities() {
  const navigate = useNavigate()
  const [year, setYear] = useState<number | undefined>()
  const [activityType, setActivityType] = useState<string | undefined>()

  const { data, isLoading } = useQuery({
    queryKey: ['activities', year, activityType],
    queryFn: () => fetchActivities(year, activityType),
  })

  if (isLoading) return <div className="p-6 text-text-secondary text-sm">Loading...</div>

  const items = data?.items ?? []

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-text-primary mb-4">Activities</h2>

      <TypeFilter types={data?.types ?? []} selected={activityType} onChange={setActivityType} />
      <YearFilter years={data?.years ?? []} selected={year} onChange={setYear} />
      <div className="text-xs text-text-secondary mb-3">{data?.total ?? 0} activities</div>

      <div className="bg-bg-card border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-bg-secondary">
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Date</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Title</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Type</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Duration</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Dist (km)</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Elev (m)</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {items.map(a => (
              <tr
                key={a.id}
                className="border-b border-border last:border-0 hover:bg-bg-hover cursor-pointer"
                onClick={() => navigate(`/activity/${a.id}`)}
              >
                <td className="px-3 py-2 text-text-secondary text-xs whitespace-nowrap">
                  {a.date ? formatDate(a.date) : ''}
                </td>
                <td className="px-3 py-2 font-medium text-text-primary">
                  {a.title || ''}
                </td>
                <td className="px-3 py-2 text-text-secondary">
                  {a.activity_type ? a.activity_type.charAt(0).toUpperCase() + a.activity_type.slice(1) : ''}
                </td>
                <td className="px-3 py-2 text-right text-text-secondary">
                  {formatDuration(a.moving_time_seconds ?? a.duration_seconds)}
                </td>
                <td className="px-3 py-2 text-right text-text-secondary">
                  {formatDistance(a.distance_km)}
                </td>
                <td className="px-3 py-2 text-right text-text-secondary">
                  {a.elevation_gain != null ? `+${Math.round(a.elevation_gain)}` : ''}
                </td>
                <td className="px-3 py-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    a.source === 'strava' ? 'bg-orange-500/20 text-orange-400' : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {a.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <div className="text-center text-text-secondary py-8">No activities found</div>
        )}
      </div>
    </div>
  )
}
