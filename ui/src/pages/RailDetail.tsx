import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchRailJourney, updateRailJourney, deleteRailJourney, createRailJourney, type RailJourneyUpdate, type RailJourneyCreate } from '../api/transport'
import RailForm from '../components/RailForm'

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatTime(t: string | null): string | null {
  if (!t) return null
  return t.slice(0, 5)
}

function currencySymbol(c: string | null): string {
  if (!c) return ''
  const map: Record<string, string> = { GBP: '\u00a3', EUR: '\u20ac', USD: '$', CHF: 'CHF ' }
  return map[c.toUpperCase()] ?? c + ' '
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

export default function RailDetail() {
  const { id } = useParams<{ id: string }>()
  const isNew = id === 'new'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(isNew)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: journey, isLoading } = useQuery({
    queryKey: ['rail-journey', id],
    queryFn: () => fetchRailJourney(Number(id)),
    enabled: !!id && !isNew,
  })

  const create = useMutation({
    mutationFn: (form: {
      date: string; time: string; from_station: string; from_code: string;
      to_station: string; to_code: string; operator: string; ticket_type: string;
      direction: string; train: string; via: string; reference: string;
      price: string; currency: string
    }) => {
      const data: RailJourneyCreate = {
        date: form.date,
        from_station: form.from_station,
        to_station: form.to_station,
        time: form.time || null,
        from_code: form.from_code || null,
        to_code: form.to_code || null,
        operator: form.operator || null,
        ticket_type: form.ticket_type || null,
        direction: form.direction || null,
        train: form.train || null,
        via: form.via || null,
        reference: form.reference || null,
        price: form.price ? parseFloat(form.price) : null,
        currency: form.currency || null,
      }
      return createRailJourney(data)
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['rail-journeys'] })
      navigate(`/travel/rail/${result.id}`, { replace: true })
    },
  })

  const update = useMutation({
    mutationFn: (form: {
      date: string; time: string; from_station: string; from_code: string;
      to_station: string; to_code: string; operator: string; ticket_type: string;
      direction: string; train: string; via: string; reference: string;
      price: string; currency: string
    }) =>
      updateRailJourney(Number(id), {
        date: form.date || null,
        time: form.time || null,
        from_station: form.from_station || null,
        from_code: form.from_code || null,
        to_station: form.to_station || null,
        to_code: form.to_code || null,
        operator: form.operator || null,
        ticket_type: form.ticket_type || null,
        direction: form.direction || null,
        train: form.train || null,
        via: form.via || null,
        reference: form.reference || null,
        price: form.price ? parseFloat(form.price) : null,
        currency: form.currency || null,
      } as RailJourneyUpdate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rail-journey', id] })
      setEditing(false)
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteRailJourney(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rail-journeys'] })
      navigate('/travel')
    },
  })

  if (!isNew && isLoading) return <div className="p-6 text-text-secondary">Loading...</div>
  if (!isNew && !journey) return <div className="p-6 text-text-secondary">Rail journey not found</div>

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
          <h3 className="text-sm font-medium text-text-primary mb-3">{isNew ? 'New Rail Journey' : 'Edit Rail Journey'}</h3>
          <RailForm
            initial={isNew ? {} : {
              date: journey!.date,
              time: journey!.time ?? '',
              from_station: journey!.from_station,
              from_code: journey!.from_code ?? '',
              to_station: journey!.to_station,
              to_code: journey!.to_code ?? '',
              operator: journey!.operator ?? '',
              ticket_type: journey!.ticket_type ?? '',
              direction: journey!.direction ?? '',
              train: journey!.train ?? '',
              via: journey!.via ?? '',
              reference: journey!.reference ?? '',
              price: journey!.price != null ? String(journey!.price) : '',
              currency: journey!.currency ?? 'GBP',
            }}
            onSubmit={form => isNew ? create.mutate(form) : update.mutate(form)}
            onCancel={() => isNew ? navigate('/travel') : setEditing(false)}
            submitLabel={isNew ? 'Create' : 'Update'}
          />
        </div>
      ) : (() => { const j = journey!; return (
        <>
          {/* Header */}
          <div className="mb-4">
            <h2 className="text-xl font-bold text-text-primary">
              {j.from_station} &rarr; {j.to_station}
            </h2>
            <div className="text-sm text-text-secondary mt-1">
              {formatDate(j.date)}
            </div>
          </div>

          {/* Journey info */}
          <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
            <Row
              label="From"
              value={j.from_code
                ? `${j.from_station} (${j.from_code})`
                : j.from_station}
            />
            <Row
              label="To"
              value={j.to_code
                ? `${j.to_station} (${j.to_code})`
                : j.to_station}
            />
            <Row label="Time" value={formatTime(j.time)} />
            <Row label="Train" value={j.train} />
            <Row label="Via" value={j.via} />
            <Row label="Direction" value={j.direction} />
          </div>

          {/* Ticket info */}
          <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
            <Row label="Operator" value={j.operator} />
            <Row label="Ticket Type" value={j.ticket_type} />
            <Row label="Reference" value={j.reference} />
            <Row
              label="Price"
              value={j.price != null
                ? `${currencySymbol(j.currency)}${j.price.toFixed(2)}`
                : null}
            />
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
                <span className="text-xs text-red-600">Delete this journey?</span>
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
