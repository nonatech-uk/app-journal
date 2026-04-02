import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchEvents, createEvent } from '../api/events'
import EventForm from '../components/EventForm'

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

const TYPE_COLOURS: Record<string, string> = {
  meal: 'bg-orange-100 text-orange-700',
  restaurant: 'bg-orange-100 text-orange-700',
  show: 'bg-purple-100 text-purple-700',
  lecture: 'bg-blue-100 text-blue-700',
  concert: 'bg-pink-100 text-pink-700',
  jazz: 'bg-indigo-100 text-indigo-700',
  sport: 'bg-green-100 text-green-700',
  hotel: 'bg-cyan-100 text-cyan-700',
  festival: 'bg-yellow-100 text-yellow-700',
  workshop: 'bg-teal-100 text-teal-700',
  other: 'bg-gray-100 text-gray-600',
}

export default function Events() {
  const [selectedYear, setSelectedYear] = useState<number | undefined>()
  const [selectedType, setSelectedType] = useState<string | undefined>()
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['events', selectedYear, selectedType],
    queryFn: () => fetchEvents({ year: selectedYear, event_type: selectedType }),
  })

  const create = useMutation({
    mutationFn: (form: {
      title: string; event_date: string; end_date: string; event_type: string;
      notes: string; fuzzy_date: boolean; latitude: string; longitude: string;
      place_id: number | null; trip_id: number | null
    }) =>
      createEvent({
        title: form.title,
        event_date: form.event_date,
        end_date: form.end_date || null,
        event_type: form.event_type,
        notes: form.notes || null,
        fuzzy_date: form.fuzzy_date,
        latitude: form.latitude ? parseFloat(form.latitude) : null,
        longitude: form.longitude ? parseFloat(form.longitude) : null,
        place_id: form.place_id,
        trip_id: form.trip_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      setShowCreate(false)
    },
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading events...</div>

  const events = data?.items ?? []
  const years = data?.years ?? []
  const types = data?.types ?? []

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">
          Events {selectedYear ? `(${selectedYear})` : ''} — {data?.total ?? 0}
        </h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent-hover transition-colors"
        >
          {showCreate ? 'Cancel' : '+ Add Event'}
        </button>
      </div>

      {showCreate && (
        <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-medium text-text-primary mb-3">New Event</h3>
          <EventForm
            onSubmit={form => create.mutate(form)}
            onCancel={() => setShowCreate(false)}
            submitLabel="Create"
          />
          {create.isError && (
            <div className="mt-2 text-xs text-red-600">
              Failed to create event: {(create.error as Error).message}
            </div>
          )}
        </div>
      )}

      {/* Year filter */}
      <div className="flex flex-wrap gap-1.5 mb-3">
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

      {/* Type filter */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <button
          className={`px-2 py-1 text-xs rounded ${
            !selectedType ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
          }`}
          onClick={() => setSelectedType(undefined)}
        >
          All types
        </button>
        {types.map(t => (
          <button
            key={t.type}
            className={`px-2 py-1 text-xs rounded ${
              selectedType === t.type ? 'bg-accent text-white' : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
            }`}
            onClick={() => setSelectedType(t.type)}
          >
            {t.type.charAt(0).toUpperCase() + t.type.slice(1)} ({t.count})
          </button>
        ))}
      </div>

      {/* Event grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {events.map(ev => (
          <div
            key={ev.id}
            className="bg-bg-card border border-border rounded-lg p-4 hover:border-accent/50 cursor-pointer transition-colors"
            onClick={() => navigate(`/event/${ev.id}`)}
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-medium text-text-primary text-sm truncate flex-1">{ev.title}</h3>
              <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${TYPE_COLOURS[ev.event_type] ?? TYPE_COLOURS.other}`}>
                {ev.event_type}
              </span>
            </div>
            <div className="text-xs text-text-secondary mt-1">
              {ev.fuzzy_date ? '~' : ''}{formatDate(ev.event_date)}
              {ev.end_date && ev.end_date !== ev.event_date && ` — ${formatDate(ev.end_date)}`}
            </div>
            {ev.place_label && ev.latitude != null && ev.longitude != null ? (
              <a
                href={`https://www.openstreetmap.org/?mlat=${ev.latitude}&mlon=${ev.longitude}#map=16/${ev.latitude}/${ev.longitude}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent hover:underline mt-1 block"
                onClick={e => e.stopPropagation()}
              >
                {ev.place_label}
              </a>
            ) : ev.place_label ? (
              <div className="text-xs text-text-secondary mt-1">{ev.place_label}</div>
            ) : null}
            {ev.trip_title && (
              <div className="text-xs text-accent mt-1">{ev.trip_title}</div>
            )}
            {ev.notes && (
              <div className="text-xs text-text-secondary mt-2 line-clamp-2">{ev.notes}</div>
            )}
          </div>
        ))}
      </div>

      {events.length === 0 && (
        <div className="text-center text-text-secondary py-12">No events found</div>
      )}
    </div>
  )
}
