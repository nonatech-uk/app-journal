import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchFlight, updateFlight, deleteFlight, createFlight, flightImageUrl, type FlightUpdate, type FlightCreate } from '../api/transport'
import FlightForm from '../components/FlightForm'
import ImageLightbox from '../components/ImageLightbox'

const CLASS_LABELS: Record<number, string> = { 1: 'Economy', 2: 'Business', 3: 'First', 4: 'Economy Plus' }
const SEAT_TYPE_LABELS: Record<number, string> = { 1: 'Window', 2: 'Middle', 3: 'Aisle' }
const REASON_LABELS: Record<number, string> = { 1: 'Leisure', 2: 'Business' }

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatTime(t: string | null): string {
  if (!t) return ''
  return t.slice(0, 5)
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null
  return (
    <div className="flex justify-between py-1.5 border-b border-border last:border-0">
      <span className="text-text-secondary text-sm">{label}</span>
      <span className="text-text-primary text-sm font-medium">{value}</span>
    </div>
  )
}

export default function FlightDetail() {
  const { id } = useParams<{ id: string }>()
  const isNew = id === 'new'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(isNew)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null)
  const [lightboxAlt, setLightboxAlt] = useState('')

  const { data: flight, isLoading } = useQuery({
    queryKey: ['flight', id],
    queryFn: () => fetchFlight(Number(id)),
    enabled: !!id && !isNew,
  })

  const create = useMutation({
    mutationFn: (form: {
      date: string; dep_airport: string; arr_airport: string;
      flight_number: string; airline: string; aircraft_type: string;
      registration: string; seat_number: string; seat_type: number | null;
      flight_class: number | null; flight_reason: number | null;
      notes: string; dep_time: string; arr_time: string;
      is_route: boolean; times_flown: string
    }) => {
      const data: FlightCreate = {
        date: form.date,
        dep_airport: form.dep_airport,
        arr_airport: form.arr_airport,
        flight_number: form.flight_number || null,
        airline: form.airline || null,
        aircraft_type: form.aircraft_type || null,
        registration: form.registration || null,
        seat_number: form.seat_number || null,
        seat_type: form.seat_type,
        flight_class: form.flight_class,
        flight_reason: form.flight_reason,
        notes: form.notes || null,
        dep_time: form.dep_time || null,
        arr_time: form.arr_time || null,
      }
      return createFlight(data)
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['flights'] })
      navigate(`/travel/flights/${result.id}`, { replace: true })
    },
  })

  const update = useMutation({
    mutationFn: (form: {
      date: string; dep_airport: string; arr_airport: string;
      flight_number: string; airline: string; aircraft_type: string;
      registration: string; seat_number: string; seat_type: number | null;
      flight_class: number | null; flight_reason: number | null;
      notes: string; dep_time: string; arr_time: string;
      is_route: boolean; times_flown: string
    }) => {
      const data: FlightUpdate = {
        flight_number: form.flight_number || null,
        airline: form.airline || null,
        aircraft_type: form.aircraft_type || null,
        registration: form.registration || null,
        seat_number: form.seat_number || null,
        seat_type: form.seat_type,
        flight_class: form.flight_class,
        flight_reason: form.flight_reason,
        notes: form.notes || null,
        is_route: form.is_route,
        times_flown: form.times_flown ? Number(form.times_flown) : null,
      }
      return updateFlight(Number(id), data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flight', id] })
      setEditing(false)
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteFlight(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flights'] })
      navigate('/travel')
    },
  })

  if (!isNew && isLoading) return <div className="p-6 text-text-secondary">Loading...</div>
  if (!isNew && !flight) return <div className="p-6 text-text-secondary">Flight not found</div>

  const hasOperational = flight && (flight!.gate_origin || flight!.gate_destination ||
    flight!.terminal_origin || flight!.terminal_destination ||
    flight!.baggage_claim || flight!.departure_delay != null ||
    flight!.arrival_delay != null || flight!.codeshares)

  return (
    <div className="p-6 max-w-3xl">
      {/* Back */}
      <button
        onClick={() => navigate('/travel')}
        className="text-sm text-text-secondary hover:text-text-primary mb-4 inline-block"
      >
        &larr; Travel
      </button>

      {editing ? (
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-primary mb-3">{isNew ? 'New Flight' : 'Edit Flight'}</h3>
          <FlightForm
            initial={isNew ? {} : {
              date: flight!.date,
              dep_airport: flight!.dep_airport,
              arr_airport: flight!.arr_airport,
              flight_number: flight!.flight_number ?? '',
              airline: flight!.airline ?? '',
              aircraft_type: flight!.aircraft_type ?? '',
              registration: flight!.registration ?? '',
              seat_number: flight!.seat_number ?? '',
              seat_type: flight!.seat_type,
              flight_class: flight!.flight_class,
              flight_reason: flight!.flight_reason,
              notes: flight!.notes ?? '',
              dep_time: flight!.dep_time ? flight!.dep_time.slice(0, 5) : '',
              arr_time: flight!.arr_time ? flight!.arr_time.slice(0, 5) : '',
              is_route: flight!.is_route,
              times_flown: flight!.times_flown != null ? String(flight!.times_flown) : '',
            }}
            onSubmit={form => isNew ? create.mutate(form) : update.mutate(form)}
            onCancel={() => isNew ? navigate('/travel') : setEditing(false)}
            submitLabel={isNew ? 'Create' : 'Update'}
          />
        </div>
      ) : (() => { const f = flight!; return (
        <>
          {/* Header */}
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                {f.dep_airport} &rarr; {f.arr_airport}
              </h2>
              <div className="text-sm text-text-secondary mt-1">
                {formatDate(f.date)}
              </div>
            </div>
            {f.airline && (
              <span className="text-xs px-2 py-1 rounded shrink-0 bg-blue-100 text-blue-700">
                {f.airline}
              </span>
            )}
          </div>

          {/* Route info */}
          <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
            <Row
              label="From"
              value={
                f.dep_airport_name
                  ? `${f.dep_airport_name} (${f.dep_airport}${f.dep_icao ? '/' + f.dep_icao : ''})`
                  : f.dep_airport
              }
            />
            <Row
              label="To"
              value={
                f.arr_airport_name
                  ? `${f.arr_airport_name} (${f.arr_airport}${f.arr_icao ? '/' + f.arr_icao : ''})`
                  : f.arr_airport
              }
            />
            <Row
              label="Times"
              value={
                (f.dep_time || f.arr_time)
                  ? `${formatTime(f.dep_time)} – ${formatTime(f.arr_time)}`
                  : null
              }
            />
            <Row label="Duration" value={f.duration} />
            <Row label="Distance" value={f.distance_km != null ? `${f.distance_km} km` : null} />
          </div>

          {/* Flight info */}
          <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
            <Row label="Flight" value={f.flight_number} />
            <Row label="Airline" value={f.airline} />
            <Row
              label="Aircraft"
              value={
                f.aircraft_type
                  ? f.registration
                    ? <Link to={`/aircraft/${encodeURIComponent(f.registration)}`} className="text-accent hover:underline">{f.aircraft_type}</Link>
                    : f.aircraft_type
                  : null
              }
            />
            <Row
              label="Registration"
              value={
                f.registration
                  ? <Link to={`/aircraft/${encodeURIComponent(f.registration)}`} className="text-accent hover:underline">{f.registration}</Link>
                  : null
              }
            />
            <Row
              label="Seat"
              value={
                f.seat_number
                  ? f.seat_type
                    ? `${f.seat_number} (${SEAT_TYPE_LABELS[f.seat_type] ?? ''})`
                    : f.seat_number
                  : f.seat_type
                    ? SEAT_TYPE_LABELS[f.seat_type]
                    : null
              }
            />
            <Row label="Class" value={f.flight_class != null ? CLASS_LABELS[f.flight_class] : null} />
            <Row label="Reason" value={f.flight_reason != null ? REASON_LABELS[f.flight_reason] : null} />
          </div>

          {/* Operational */}
          {hasOperational && (
            <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
              <Row label="Gate Origin" value={f.gate_origin} />
              <Row label="Gate Dest" value={f.gate_destination} />
              <Row label="Terminal Origin" value={f.terminal_origin} />
              <Row label="Terminal Dest" value={f.terminal_destination} />
              <Row label="Baggage" value={f.baggage_claim} />
              <Row
                label="Departure Delay"
                value={f.departure_delay != null ? `${f.departure_delay} min` : null}
              />
              <Row
                label="Arrival Delay"
                value={f.arrival_delay != null ? `${f.arrival_delay} min` : null}
              />
              <Row label="Codeshares" value={f.codeshares} />
            </div>
          )}

          {/* Notes */}
          {f.notes && (
            <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
              <div className="text-sm text-text-primary whitespace-pre-wrap">{f.notes}</div>
            </div>
          )}

          {/* Images */}
          {(f.has_route_image || f.has_aircraft_image) && (
            <div className="flex gap-3 mb-4">
              {f.has_route_image && (
                <img
                  src={flightImageUrl(f.id, 'route', 'thumb')}
                  alt="Route"
                  className="h-24 rounded border border-border cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => {
                    setLightboxSrc(flightImageUrl(f.id, 'route', 'full'))
                    setLightboxAlt('Route')
                  }}
                />
              )}
              {f.has_aircraft_image && (
                <img
                  src={flightImageUrl(f.id, 'aircraft', 'thumb')}
                  alt="Aircraft"
                  className="h-24 rounded border border-border cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => {
                    setLightboxSrc(flightImageUrl(f.id, 'aircraft', 'full'))
                    setLightboxAlt('Aircraft')
                  }}
                />
              )}
            </div>
          )}

          {lightboxSrc && (
            <ImageLightbox
              src={lightboxSrc}
              alt={lightboxAlt}
              onClose={() => setLightboxSrc(null)}
            />
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-primary hover:bg-bg-hover border border-border transition-colors"
            >
              Edit
            </button>
            {confirmDelete ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-600">Delete this flight?</span>
                <button
                  onClick={() => remove.mutate()}
                  className="px-3 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-hover border border-border transition-colors"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmDelete(true)}
                className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-red-600 hover:bg-red-50 border border-border transition-colors"
              >
                Delete
              </button>
            )}
          </div>
        </>
      ); })()}
    </div>
  )
}
