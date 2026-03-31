import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'

interface TripSummary {
  id: number
  title: string
  start_date: string
  end_date: string
  countries: string[]
  locations: string[]
  entry_count: number
  duration_days: number
  immich_album_id: string | null
  cover_asset_id: string | null
}

interface TripsResponse {
  items: TripSummary[]
  total: number
  years: { year: number; count: number }[]
}

function fetchTrips(year?: number): Promise<TripsResponse> {
  const params = year ? `?year=${year}&limit=200` : '?limit=200'
  return apiFetch<TripsResponse>(`/trips${params}`)
}

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

export default function Trips() {
  const [selectedYear, setSelectedYear] = useState<number | undefined>()
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['trips', selectedYear],
    queryFn: () => fetchTrips(selectedYear),
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading trips...</div>

  const trips = data?.items ?? []
  const years = data?.years ?? []

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">
          Trips {selectedYear ? `(${selectedYear})` : ''} — {data?.total ?? 0}
        </h2>
      </div>

      {/* Year filter */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <button
          className={`px-2 py-1 text-xs rounded ${
            !selectedYear ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
          }`}
          onClick={() => setSelectedYear(undefined)}
        >
          All
        </button>
        {years.map(y => (
          <button
            key={y.year}
            className={`px-2 py-1 text-xs rounded ${
              selectedYear === y.year ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
            }`}
            onClick={() => setSelectedYear(y.year)}
          >
            {y.year} ({y.count})
          </button>
        ))}
      </div>

      {/* Trip grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {trips.map(trip => (
          <div
            key={trip.id}
            className="bg-bg-card border border-border rounded-lg p-4 hover:border-accent/50 cursor-pointer transition-colors"
            onClick={() => navigate(`/trip/${trip.id}`)}
          >
            <h3 className="font-medium text-text-primary text-sm truncate">{trip.title}</h3>
            <div className="text-xs text-text-secondary mt-1">
              {formatDate(trip.start_date)}
              {trip.end_date !== trip.start_date && ` — ${formatDate(trip.end_date)}`}
            </div>
            <div className="flex items-center gap-2 mt-2 text-xs text-text-secondary">
              {trip.duration_days && <span>{trip.duration_days}d</span>}
              {trip.entry_count > 0 && <span>{trip.entry_count} entries</span>}
            </div>
            {trip.countries && trip.countries.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {trip.countries.map(c => (
                  <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-bg-secondary text-text-secondary">
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {trips.length === 0 && (
        <div className="text-center text-text-secondary py-12">No trips found</div>
      )}
    </div>
  )
}
