import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface TripEntry {
  entry_id: number
  day_number: number | null
  day_label: string | null
  is_travel_day: boolean
  is_rest_day: boolean
  created_at: string
  uuid: string
  preview: string | null
  place_name: string | null
  country: string | null
}

interface TripDetailData {
  id: number
  path: string
  title: string
  description: string | null
  start_date: string
  end_date: string
  countries: string[]
  locations: string[]
  companions: string[]
  cover_asset_id: string | null
  immich_album_id: string | null
  tags: string[]
  notes: string | null
  entries: TripEntry[]
  stats: { key: string; value: string; unit: string | null }[]
}

function fetchTrip(id: number): Promise<TripDetailData> {
  return apiFetch<TripDetailData>(`/trips/${id}`)
}

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  })
}

export default function TripDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const tripId = id ? Number(id) : undefined
  const { data: trip, isLoading } = useQuery({
    queryKey: ['trip', tripId],
    queryFn: () => fetchTrip(tripId!),
    enabled: !!tripId,
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading...</div>
  if (!trip) return <div className="p-6 text-text-secondary">Trip not found</div>

  const durationDays = trip.start_date && trip.end_date
    ? Math.ceil((new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) / 86400000) + 1
    : null

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <button
        onClick={() => navigate('/trips')}
        className="text-xs text-text-secondary hover:text-accent mb-3 block"
      >
        &larr; Back to trips
      </button>

      <h2 className="text-2xl font-bold text-text-primary">{trip.title}</h2>

      <div className="text-sm text-text-secondary mt-1">
        {formatDate(trip.start_date)}
        {trip.end_date !== trip.start_date && ` — ${formatDate(trip.end_date)}`}
        {durationDays && <span className="ml-2">({durationDays} days)</span>}
      </div>

      {/* Countries & locations */}
      {trip.countries && trip.countries.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {trip.countries.map(c => (
            <span key={c} className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent">
              {c}
            </span>
          ))}
        </div>
      )}

      {trip.locations && trip.locations.length > 0 && (
        <div className="text-xs text-text-secondary mt-2">
          {trip.locations.join(' · ')}
        </div>
      )}

      {/* Description / notes */}
      {trip.description && (
        <p className="text-sm text-text-primary mt-4">{trip.description}</p>
      )}
      {trip.notes && (
        <p className="text-sm text-text-secondary mt-2 italic">{trip.notes}</p>
      )}

      {/* Companions */}
      {trip.companions && trip.companions.length > 0 && (
        <div className="mt-3 text-xs text-text-secondary">
          With: {trip.companions.join(', ')}
        </div>
      )}

      {/* Stats */}
      {trip.stats && trip.stats.length > 0 && (
        <div className="mt-4 grid grid-cols-3 gap-2">
          {trip.stats.map(s => (
            <div key={s.key} className="bg-bg-card border border-border rounded p-2 text-center">
              <div className="text-lg font-bold text-text-primary">{s.value}{s.unit && <span className="text-xs text-text-secondary ml-0.5">{s.unit}</span>}</div>
              <div className="text-[10px] text-text-secondary">{s.key}</div>
            </div>
          ))}
        </div>
      )}

      {/* Entries timeline */}
      <div className="mt-6">
        <h3 className="text-sm font-medium text-text-secondary mb-3">
          Journal Entries ({trip.entries.length})
        </h3>
        {trip.entries.length === 0 ? (
          <div className="text-xs text-text-secondary italic">No journal entries linked to this trip</div>
        ) : (
          <div className="space-y-2">
            {trip.entries.map(e => (
              <div
                key={e.entry_id}
                className="bg-bg-card border border-border rounded-lg p-3 hover:border-accent/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/entry/${e.entry_id}`)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-secondary">
                    {new Date(e.created_at).toLocaleDateString('en-GB', {
                      weekday: 'short', day: 'numeric', month: 'short',
                    })}
                  </span>
                  {e.day_number && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-secondary text-text-secondary">
                      Day {e.day_number}
                    </span>
                  )}
                  {e.is_travel_day && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500">Travel</span>
                  )}
                  {e.place_name && (
                    <span className="text-xs text-text-secondary ml-auto">{e.place_name}</span>
                  )}
                </div>
                {e.preview && (
                  <div className="text-xs text-text-secondary mt-1 line-clamp-2">
                    {e.preview.replace(/\n/g, ' ').trim()}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
