import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface ActivityTypeOption {
  id: number
  name: string
}

interface ActivityFormData {
  title: string
  activity_type: string
  date: string
  start_time: string
  distance_km: string
  duration_seconds: string
  elevation_gain: string
  elevation_loss: string
  max_altitude: string
  notes: string
}

interface Props {
  initial?: Partial<ActivityFormData>
  onSubmit: (data: ActivityFormData) => void
  onCancel: () => void
  submitLabel?: string
}

function fetchActivityTypes(): Promise<ActivityTypeOption[]> {
  return apiFetch<ActivityTypeOption[]>('/activity-types')
}

export default function ActivityForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [form, setForm] = useState<ActivityFormData>({
    title: '',
    activity_type: 'running',
    date: new Date().toISOString().slice(0, 10),
    start_time: '',
    distance_km: '',
    duration_seconds: '',
    elevation_gain: '',
    elevation_loss: '',
    max_altitude: '',
    notes: '',
    ...initial,
  })

  const { data: typesData } = useQuery({
    queryKey: ['activity-types'],
    queryFn: fetchActivityTypes,
  })
  const types = typesData ?? []

  useEffect(() => {
    if (initial) setForm(prev => ({ ...prev, ...initial }))
  }, [initial])

  const set = (field: keyof ActivityFormData, value: string) =>
    setForm(prev => ({ ...prev, [field]: value }))

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
            value={form.date}
            onChange={e => set('date', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Type</label>
          <select
            value={form.activity_type}
            onChange={e => set('activity_type', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          >
            {types.map(t => (
              <option key={t.name} value={t.name}>
                {t.name.charAt(0).toUpperCase() + t.name.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Start time</label>
          <input
            type="time"
            value={form.start_time}
            onChange={e => set('start_time', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Duration (minutes)</label>
          <input
            type="number"
            value={form.duration_seconds ? String(Math.round(Number(form.duration_seconds) / 60)) : ''}
            onChange={e => set('duration_seconds', e.target.value ? String(Number(e.target.value) * 60) : '')}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Distance (km)</label>
          <input
            type="number"
            step="0.1"
            value={form.distance_km}
            onChange={e => set('distance_km', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Elev. gain (m)</label>
          <input
            type="number"
            value={form.elevation_gain}
            onChange={e => set('elevation_gain', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Elev. loss (m)</label>
          <input
            type="number"
            value={form.elevation_loss}
            onChange={e => set('elevation_loss', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
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
          disabled={!form.title.trim() || !form.date}
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
