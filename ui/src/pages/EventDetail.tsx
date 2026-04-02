import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchEvent, updateEvent, deleteEvent, linkDocument, unlinkDocument } from '../api/events'
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

export default function EventDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [newDocId, setNewDocId] = useState('')
  const [newDocLabel, setNewDocLabel] = useState('')

  const { data: event, isLoading } = useQuery({
    queryKey: ['event', id],
    queryFn: () => fetchEvent(Number(id)),
    enabled: !!id,
  })

  const update = useMutation({
    mutationFn: (form: {
      title: string; event_date: string; end_date: string; event_type: string;
      notes: string; fuzzy_date: boolean; latitude: string; longitude: string;
      place_id: number | null; trip_id: number | null
    }) =>
      updateEvent(Number(id), {
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
      queryClient.invalidateQueries({ queryKey: ['event', id] })
      setEditing(false)
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteEvent(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      navigate('/events')
    },
  })

  const addDoc = useMutation({
    mutationFn: () => linkDocument(Number(id), Number(newDocId), newDocLabel || null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', id] })
      setNewDocId('')
      setNewDocLabel('')
    },
  })

  const removeDoc = useMutation({
    mutationFn: (paperlessId: number) => unlinkDocument(Number(id), paperlessId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['event', id] }),
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading...</div>
  if (!event) return <div className="p-6 text-text-secondary">Event not found</div>

  return (
    <div className="p-6 max-w-3xl">
      {/* Back */}
      <button
        onClick={() => navigate('/events')}
        className="text-sm text-text-secondary hover:text-text-primary mb-4 inline-block"
      >
        &larr; Events
      </button>

      {editing ? (
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-primary mb-3">Edit Event</h3>
          <EventForm
            initial={{
              title: event.title,
              event_date: event.event_date,
              end_date: event.end_date ?? '',
              event_type: event.event_type,
              notes: event.notes ?? '',
              fuzzy_date: event.fuzzy_date,
              latitude: event.latitude != null ? String(event.latitude) : '',
              longitude: event.longitude != null ? String(event.longitude) : '',
              place_id: event.place_id,
              trip_id: event.trip_id,
            }}
            onSubmit={form => update.mutate(form)}
            onCancel={() => setEditing(false)}
            submitLabel="Update"
          />
        </div>
      ) : (
        <>
          {/* Header */}
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h2 className="text-xl font-bold text-text-primary">{event.title}</h2>
              <div className="text-sm text-text-secondary mt-1">
                {event.fuzzy_date ? '~' : ''}{formatDate(event.event_date)}
                {event.end_date && event.end_date !== event.event_date && ` — ${formatDate(event.end_date)}`}
              </div>
            </div>
            <span className={`text-xs px-2 py-1 rounded shrink-0 ${TYPE_COLOURS[event.event_type] ?? TYPE_COLOURS.other}`}>
              {event.event_type}
            </span>
          </div>

          {/* Meta */}
          <div className="space-y-2 mb-4">
            {event.latitude != null && event.longitude != null && (
              <div className="text-sm">
                <span className="text-text-primary font-medium">Location:</span>{' '}
                <a
                  href={`https://www.openstreetmap.org/?mlat=${event.latitude}&mlon=${event.longitude}#map=17/${event.latitude}/${event.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  {event.place_label || `${event.latitude.toFixed(4)}, ${event.longitude.toFixed(4)}`}
                </a>
              </div>
            )}
            {event.place_label && event.latitude == null && (
              <div className="text-sm text-text-secondary">
                <span className="text-text-primary font-medium">Place:</span> {event.place_label}
              </div>
            )}
            {event.trip_id && (
              <div className="text-sm">
                <span className="text-text-primary font-medium">Trip:</span>{' '}
                <Link to={`/trip/${event.trip_id}`} className="text-accent hover:underline">
                  {event.trip_title}
                </Link>
              </div>
            )}
          </div>

          {/* Notes */}
          {event.notes && (
            <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
              <div className="text-sm text-text-primary whitespace-pre-wrap">{event.notes}</div>
            </div>
          )}

          {/* Documents */}
          <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
            <h3 className="text-sm font-medium text-text-primary mb-2">Documents</h3>
            {event.documents.length > 0 ? (
              <div className="space-y-1.5 mb-3">
                {event.documents.map(doc => (
                  <div key={doc.paperless_id} className="flex items-center justify-between text-sm">
                    <span className="text-text-primary">
                      Paperless #{doc.paperless_id}
                      {doc.label && <span className="text-text-secondary ml-1">({doc.label})</span>}
                    </span>
                    <button
                      onClick={() => removeDoc.mutate(doc.paperless_id)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-text-secondary mb-3">No documents linked</div>
            )}
            <div className="flex gap-2 items-end">
              <div>
                <label className="block text-xs text-text-secondary mb-1">Paperless ID</label>
                <input
                  type="number"
                  value={newDocId}
                  onChange={e => setNewDocId(e.target.value)}
                  className="w-24 bg-bg-secondary border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">Label</label>
                <input
                  type="text"
                  value={newDocLabel}
                  onChange={e => setNewDocLabel(e.target.value)}
                  placeholder="receipt, ticket..."
                  className="w-32 bg-bg-secondary border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                />
              </div>
              <button
                onClick={() => addDoc.mutate()}
                disabled={!newDocId}
                className="px-2 py-1 text-sm rounded bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
              >
                Link
              </button>
            </div>
          </div>

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
                <span className="text-xs text-red-600">Delete this event?</span>
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
      )}
    </div>
  )
}
