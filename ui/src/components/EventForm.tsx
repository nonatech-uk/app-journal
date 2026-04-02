import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { fetchPlaces } from '../api/places'

interface TripOption {
  id: number
  title: string
  start_date: string
}

interface EventFormData {
  title: string
  event_date: string
  end_date: string
  event_type: string
  notes: string
  fuzzy_date: boolean
  latitude: string
  longitude: string
  place_id: number | null
  trip_id: number | null
}

interface Props {
  initial?: Partial<EventFormData>
  onSubmit: (data: EventFormData) => void
  onCancel: () => void
  submitLabel?: string
}

interface EventTypeOption {
  id: number
  name: string
  event_count: number
}

function fetchTripsForSelect(): Promise<{ items: TripOption[] }> {
  return apiFetch<{ items: TripOption[] }>('/trips?limit=500')
}

function fetchEventTypes(): Promise<EventTypeOption[]> {
  return apiFetch<EventTypeOption[]>('/event-types')
}

export default function EventForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [form, setForm] = useState<EventFormData>({
    title: '',
    event_date: new Date().toISOString().slice(0, 10),
    end_date: '',
    event_type: 'other',
    notes: '',
    fuzzy_date: false,
    latitude: '',
    longitude: '',
    place_id: null,
    trip_id: null,
    ...initial,
  })
  const [placeSearch, setPlaceSearch] = useState('')

  const { data: tripsData } = useQuery({
    queryKey: ['trips-select'],
    queryFn: fetchTripsForSelect,
  })
  const trips = tripsData?.items ?? []

  const { data: eventTypesData } = useQuery({
    queryKey: ['event-types'],
    queryFn: fetchEventTypes,
  })
  const eventTypes = eventTypesData ?? []

  const { data: placesData } = useQuery({
    queryKey: ['places'],
    queryFn: fetchPlaces,
  })
  const places = placesData?.items ?? []

  const filteredPlaces = useMemo(() => {
    if (!placeSearch.trim()) return places
    const q = placeSearch.toLowerCase()
    return places.filter(p => p.name.toLowerCase().includes(q))
  }, [places, placeSearch])

  useEffect(() => {
    if (initial) setForm(prev => ({ ...prev, ...initial }))
  }, [initial])

  const set = (field: keyof EventFormData, value: string | boolean | number | null) =>
    setForm(prev => ({ ...prev, [field]: value }))

  const selectedPlace = places.find(p => p.id === form.place_id)

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-text-secondary mb-1">Title *</label>
        <input
          type="text"
          value={form.title}
          onChange={e => set('title', e.target.value)}
          className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          autoFocus
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Date *</label>
          <input
            type="date"
            value={form.event_date}
            onChange={e => set('event_date', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">End date</label>
          <input
            type="date"
            value={form.end_date}
            onChange={e => set('end_date', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Type</label>
          <select
            value={form.event_type}
            onChange={e => set('event_type', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          >
            {eventTypes.map(t => (
              <option key={t.name} value={t.name}>
                {t.name.charAt(0).toUpperCase() + t.name.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Trip</label>
          <select
            value={form.trip_id ?? ''}
            onChange={e => set('trip_id', e.target.value ? Number(e.target.value) : null)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          >
            <option value="">No trip</option>
            {trips.map(t => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Place picker */}
      <div>
        <label className="block text-xs text-text-secondary mb-1">Place</label>
        {selectedPlace ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-primary">{selectedPlace.name}</span>
            <span className="text-xs text-text-secondary">({selectedPlace.place_type})</span>
            <button
              onClick={() => set('place_id', null)}
              className="text-xs text-red-500 hover:text-red-700"
            >
              Clear
            </button>
          </div>
        ) : (
          <div>
            <input
              type="text"
              value={placeSearch}
              onChange={e => setPlaceSearch(e.target.value)}
              placeholder="Search places..."
              className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
            />
            {placeSearch.trim() && filteredPlaces.length > 0 && (
              <div className="mt-1 max-h-32 overflow-y-auto bg-bg-card border border-border rounded text-sm">
                {filteredPlaces.slice(0, 10).map(p => (
                  <button
                    key={p.id}
                    onClick={() => {
                      set('place_id', p.id)
                      setPlaceSearch('')
                    }}
                    className="w-full text-left px-2 py-1 hover:bg-bg-hover text-text-primary"
                  >
                    {p.name} <span className="text-xs text-text-secondary">({p.place_type})</span>
                  </button>
                ))}
              </div>
            )}
            {placeSearch.trim() && filteredPlaces.length === 0 && (
              <div className="mt-1 text-xs text-text-secondary">No places found</div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="fuzzy_date"
          checked={form.fuzzy_date}
          onChange={e => set('fuzzy_date', e.target.checked)}
          className="rounded"
        />
        <label htmlFor="fuzzy_date" className="text-xs text-text-secondary">Approximate date</label>
      </div>

      <div>
        <label className="block text-xs text-text-secondary mb-1">Notes</label>
        <textarea
          value={form.notes}
          onChange={e => set('notes', e.target.value)}
          rows={3}
          className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50 resize-y"
        />
      </div>

      <div className="flex gap-2 pt-2">
        <button
          onClick={() => onSubmit(form)}
          disabled={!form.title.trim() || !form.event_date}
          className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          {submitLabel}
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-hover border border-border transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
