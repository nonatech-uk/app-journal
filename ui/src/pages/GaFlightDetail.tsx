import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchGaFlight, updateGaFlight, deleteGaFlight, createGaFlight, flightImageUrl, type GaFlightUpdate, type GaFlightCreate } from '../api/transport'
import GaFlightForm from '../components/GaFlightForm'
import ImageLightbox from '../components/ImageLightbox'

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
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

export default function GaFlightDetail() {
  const { id } = useParams<{ id: string }>()
  const isNew = id === 'new'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(isNew)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null)
  const [lightboxAlt, setLightboxAlt] = useState('')

  const { data: flight, isLoading } = useQuery({
    queryKey: ['ga-flight', id],
    queryFn: () => fetchGaFlight(Number(id)),
    enabled: !!id && !isNew,
  })

  const create = useMutation({
    mutationFn: (form: {
      date: string; aircraft_type: string; registration: string; captain: string;
      operating_capacity: string; dep_airport: string; arr_airport: string;
      dep_time: string; arr_time: string; hours_total: string; exercise: string;
      comments: string
    }) => {
      const data: GaFlightCreate = {
        date: form.date,
        aircraft_type: form.aircraft_type || null,
        registration: form.registration || null,
        captain: form.captain || null,
        operating_capacity: form.operating_capacity || null,
        dep_airport: form.dep_airport || null,
        arr_airport: form.arr_airport || null,
        dep_time: form.dep_time || null,
        arr_time: form.arr_time || null,
        hours_total: form.hours_total ? Number(form.hours_total) : null,
        exercise: form.exercise || null,
        comments: form.comments || null,
      }
      return createGaFlight(data)
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['ga-flights'] })
      navigate(`/travel/ga/${result.id}`, { replace: true })
    },
  })

  const update = useMutation({
    mutationFn: (form: {
      date: string; aircraft_type: string; registration: string; captain: string;
      operating_capacity: string; dep_airport: string; arr_airport: string;
      dep_time: string; arr_time: string; hours_total: string; exercise: string;
      comments: string
    }) => {
      const data: GaFlightUpdate = {
        aircraft_type: form.aircraft_type || null,
        registration: form.registration || null,
        captain: form.captain || null,
        operating_capacity: form.operating_capacity || null,
        exercise: form.exercise || null,
        comments: form.comments || null,
      }
      return updateGaFlight(Number(id), data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ga-flight', id] })
      setEditing(false)
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteGaFlight(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ga-flights'] })
      navigate('/travel')
    },
  })

  if (!isNew && isLoading) return <div className="p-6 text-text-secondary">Loading...</div>
  if (!isNew && !flight) return <div className="p-6 text-text-secondary">Flight not found</div>

  const hoursEntries: { label: string; value: number | null }[] = [
    { label: 'SEP PIC', value: flight?.hours_sep_pic ?? null },
    { label: 'SEP Dual', value: flight?.hours_sep_dual ?? null },
    { label: 'MEP PIC', value: flight?.hours_mep_pic ?? null },
    { label: 'MEP Dual', value: flight?.hours_mep_dual ?? null },
    { label: 'Instrument', value: flight?.hours_instrument ?? null },
    { label: 'As Instructor', value: flight?.hours_as_instructor ?? null },
    { label: 'Simulator', value: flight?.hours_simulator ?? null },
  ]
  const visibleHours = hoursEntries.filter(h => h.value != null && h.value !== 0)

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
          <h3 className="text-sm font-medium text-text-primary mb-3">{isNew ? 'New GA Flight' : 'Edit GA Flight'}</h3>
          <GaFlightForm
            initial={isNew ? {} : {
              date: flight!.date,
              aircraft_type: flight!.aircraft_type ?? '',
              registration: flight!.registration ?? '',
              captain: flight!.captain ?? '',
              operating_capacity: flight!.operating_capacity ?? '',
              dep_airport: flight!.dep_airport ?? '',
              arr_airport: flight!.arr_airport ?? '',
              dep_time: flight!.dep_time ?? '',
              arr_time: flight!.arr_time ?? '',
              hours_total: flight!.hours_total != null ? String(flight!.hours_total) : '',
              exercise: flight!.exercise ?? '',
              comments: flight!.comments ?? '',
            }}
            onSubmit={form => isNew ? create.mutate(form) : update.mutate(form)}
            onCancel={() => isNew ? navigate('/travel') : setEditing(false)}
            submitLabel={isNew ? 'Create' : 'Update'}
          />
        </div>
      ) : (() => { const f = flight!; return (
        <>
          {/* Header */}
          <div className="mb-4">
            <h2 className="text-xl font-bold text-text-primary">
              {f.dep_airport ?? '?'} &rarr; {f.arr_airport ?? '?'}
            </h2>
            <div className="text-sm text-text-secondary mt-1">
              {formatDate(f.date)}
            </div>
          </div>

          {/* Section 1 - Flight info */}
          <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
            <Row label="Aircraft" value={f.aircraft_type} />
            <Row
              label="Registration"
              value={
                f.registration ? (
                  <Link to={`/aircraft/${f.registration}`} className="text-accent hover:underline">
                    {f.registration}
                  </Link>
                ) : null
              }
            />
            <Row label="Captain" value={f.captain} />
            <Row label="Instructor" value={f.instructor} />
            <Row label="Operating Capacity" value={f.operating_capacity} />
            <Row
              label="Times"
              value={
                f.dep_time || f.arr_time
                  ? `${f.dep_time ?? '?'} \u2013 ${f.arr_time ?? '?'}`
                  : null
              }
            />
            <Row label="Exercise" value={f.exercise} />
          </div>

          {/* Section 2 - Hours breakdown */}
          {(visibleHours.length > 0 || (f.hours_total != null && f.hours_total !== 0)) && (
            <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
              <h3 className="text-sm font-medium text-text-primary mb-2">Hours</h3>
              <div className="grid grid-cols-3 gap-x-4 gap-y-1.5">
                {visibleHours.map(h => (
                  <div key={h.label} className="flex justify-between text-sm">
                    <span className="text-text-secondary">{h.label}</span>
                    <span className="text-text-primary">{h.value}</span>
                  </div>
                ))}
                {f.hours_total != null && f.hours_total !== 0 && (
                  <div className="flex justify-between text-sm font-bold">
                    <span className="text-text-secondary">Total</span>
                    <span className="text-text-primary">{f.hours_total}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Section 3 - Comments */}
          {f.comments && (
            <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
              <h3 className="text-sm font-medium text-text-primary mb-2">Comments</h3>
              <div className="text-sm text-text-primary whitespace-pre-wrap">{f.comments}</div>
            </div>
          )}

          {/* Section 4 - Images */}
          {(f.has_route_image || f.has_aircraft_image) && (
            <div className="flex gap-3 mb-4">
              {f.has_route_image && (
                <img
                  src={flightImageUrl(f.id, 'route', 'thumb', true)}
                  alt="Route"
                  className="h-24 rounded border border-border cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => {
                    setLightboxSrc(flightImageUrl(f.id, 'route', 'full', true))
                    setLightboxAlt('Route')
                  }}
                />
              )}
              {f.has_aircraft_image && (
                <img
                  src={flightImageUrl(f.id, 'aircraft', 'thumb', true)}
                  alt={f.registration ?? 'Aircraft'}
                  className="h-24 rounded border border-border cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => {
                    setLightboxSrc(flightImageUrl(f.id, 'aircraft', 'full', true))
                    setLightboxAlt(f.registration ?? 'Aircraft')
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

          {/* Section 5 - Actions */}
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
