import { useState, useEffect } from 'react'

interface GaFlightFormData {
  date: string
  aircraft_type: string
  registration: string
  captain: string
  operating_capacity: string
  dep_airport: string
  arr_airport: string
  dep_time: string
  arr_time: string
  hours_total: string
  exercise: string
  comments: string
}

interface Props {
  initial?: Partial<GaFlightFormData>
  onSubmit: (data: GaFlightFormData) => void
  onCancel: () => void
  submitLabel?: string
}

export default function GaFlightForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [form, setForm] = useState<GaFlightFormData>({
    date: new Date().toISOString().slice(0, 10),
    aircraft_type: '',
    registration: '',
    captain: '',
    operating_capacity: '',
    dep_airport: '',
    arr_airport: '',
    dep_time: '',
    arr_time: '',
    hours_total: '',
    exercise: '',
    comments: '',
    ...initial,
  })

  useEffect(() => {
    if (initial) setForm(prev => ({ ...prev, ...initial }))
  }, [initial])

  const set = (field: keyof GaFlightFormData, value: string) =>
    setForm(prev => ({ ...prev, [field]: value }))

  return (
    <div className="space-y-3">
      {/* Row 1: Date */}
      <div>
        <label className="block text-xs text-text-secondary mb-1">Date *</label>
        <input
          type="date"
          value={form.date}
          onChange={e => set('date', e.target.value)}
          className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          autoFocus
        />
      </div>

      {/* Row 2: Dep / Arr Airport */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Dep Airport</label>
          <input
            type="text"
            value={form.dep_airport}
            onChange={e => set('dep_airport', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Arr Airport</label>
          <input
            type="text"
            value={form.arr_airport}
            onChange={e => set('arr_airport', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
      </div>

      {/* Row 3: Dep / Arr Time */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Dep Time</label>
          <input
            type="time"
            value={form.dep_time}
            onChange={e => set('dep_time', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Arr Time</label>
          <input
            type="time"
            value={form.arr_time}
            onChange={e => set('arr_time', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
      </div>

      {/* Row 4: Aircraft Type / Registration */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Aircraft Type</label>
          <input
            type="text"
            value={form.aircraft_type}
            onChange={e => set('aircraft_type', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Registration</label>
          <input
            type="text"
            value={form.registration}
            onChange={e => set('registration', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
      </div>

      {/* Row 5: Captain / Operating Capacity */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Captain</label>
          <input
            type="text"
            value={form.captain}
            onChange={e => set('captain', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Operating Capacity</label>
          <select
            value={form.operating_capacity}
            onChange={e => set('operating_capacity', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          >
            <option value="">--</option>
            <option value="PUT">PUT</option>
            <option value="P1">P1</option>
            <option value="P2">P2</option>
          </select>
        </div>
      </div>

      {/* Row 6: Hours Total / Exercise */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Hours Total</label>
          <input
            type="number"
            step="0.1"
            value={form.hours_total}
            onChange={e => set('hours_total', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Exercise</label>
          <input
            type="text"
            value={form.exercise}
            onChange={e => set('exercise', e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
          />
        </div>
      </div>

      {/* Comments */}
      <div>
        <label className="block text-xs text-text-secondary mb-1">Comments</label>
        <textarea
          value={form.comments}
          onChange={e => set('comments', e.target.value)}
          rows={3}
          className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50 resize-y"
        />
      </div>

      {/* Buttons */}
      <div className="flex gap-2 pt-2">
        <button
          onClick={() => onSubmit(form)}
          disabled={!form.date}
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
