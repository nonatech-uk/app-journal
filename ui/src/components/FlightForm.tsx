import { useState, useEffect } from 'react'

interface FlightFormData {
  date: string
  dep_airport: string
  arr_airport: string
  flight_number: string
  airline: string
  aircraft_type: string
  registration: string
  seat_number: string
  seat_type: number | null
  flight_class: number | null
  flight_reason: number | null
  notes: string
  dep_time: string
  arr_time: string
  is_route: boolean
  times_flown: string
}

interface Props {
  initial?: Partial<FlightFormData>
  onSubmit: (data: FlightFormData) => void
  onCancel: () => void
  submitLabel?: string
}

export default function FlightForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [form, setForm] = useState<FlightFormData>({
    date: new Date().toISOString().slice(0, 10),
    dep_airport: '',
    arr_airport: '',
    flight_number: '',
    airline: '',
    aircraft_type: '',
    registration: '',
    seat_number: '',
    seat_type: null,
    flight_class: null,
    flight_reason: null,
    notes: '',
    dep_time: '',
    arr_time: '',
    is_route: false,
    times_flown: '',
    ...initial,
  })

  useEffect(() => {
    if (initial) setForm(prev => ({ ...prev, ...initial }))
  }, [initial])

  const set = (field: keyof FlightFormData, value: string | boolean | number | null) =>
    setForm(prev => ({ ...prev, [field]: value }))

  const inputClass = 'w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50'
  const labelClass = 'block text-xs text-text-secondary mb-1'

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Date *</label>
          <input
            type="date"
            value={form.date}
            onChange={e => set('date', e.target.value)}
            className={inputClass}
            autoFocus
          />
        </div>
        <div />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Departure Airport *</label>
          <input
            type="text"
            value={form.dep_airport}
            onChange={e => set('dep_airport', e.target.value)}
            className={inputClass}
            placeholder="LHR"
          />
        </div>
        <div>
          <label className={labelClass}>Arrival Airport *</label>
          <input
            type="text"
            value={form.arr_airport}
            onChange={e => set('arr_airport', e.target.value)}
            className={inputClass}
            placeholder="JFK"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Dep Time</label>
          <input
            type="time"
            value={form.dep_time}
            onChange={e => set('dep_time', e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Arr Time</label>
          <input
            type="time"
            value={form.arr_time}
            onChange={e => set('arr_time', e.target.value)}
            className={inputClass}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Flight Number</label>
          <input
            type="text"
            value={form.flight_number}
            onChange={e => set('flight_number', e.target.value)}
            className={inputClass}
            placeholder="BA178"
          />
        </div>
        <div>
          <label className={labelClass}>Airline</label>
          <input
            type="text"
            value={form.airline}
            onChange={e => set('airline', e.target.value)}
            className={inputClass}
            placeholder="British Airways"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Aircraft Type</label>
          <input
            type="text"
            value={form.aircraft_type}
            onChange={e => set('aircraft_type', e.target.value)}
            className={inputClass}
            placeholder="A380"
          />
        </div>
        <div>
          <label className={labelClass}>Registration</label>
          <input
            type="text"
            value={form.registration}
            onChange={e => set('registration', e.target.value)}
            className={inputClass}
            placeholder="G-XLEA"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Seat Number</label>
          <input
            type="text"
            value={form.seat_number}
            onChange={e => set('seat_number', e.target.value)}
            className={inputClass}
            placeholder="12A"
          />
        </div>
        <div>
          <label className={labelClass}>Seat Type</label>
          <select
            value={form.seat_type ?? ''}
            onChange={e => set('seat_type', e.target.value ? Number(e.target.value) : null)}
            className={inputClass}
          >
            <option value="">--</option>
            <option value="1">Window</option>
            <option value="2">Middle</option>
            <option value="3">Aisle</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Class</label>
          <select
            value={form.flight_class ?? ''}
            onChange={e => set('flight_class', e.target.value ? Number(e.target.value) : null)}
            className={inputClass}
          >
            <option value="">--</option>
            <option value="1">Economy</option>
            <option value="2">Business</option>
            <option value="3">First</option>
            <option value="4">Economy Plus</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>Reason</label>
          <select
            value={form.flight_reason ?? ''}
            onChange={e => set('flight_reason', e.target.value ? Number(e.target.value) : null)}
            className={inputClass}
          >
            <option value="">--</option>
            <option value="1">Leisure</option>
            <option value="2">Business</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_route"
            checked={form.is_route}
            onChange={e => set('is_route', e.target.checked)}
            className="rounded"
          />
          <label htmlFor="is_route" className="text-xs text-text-secondary">Route (not a specific flight)</label>
        </div>
        {form.is_route && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-text-secondary">Times flown</label>
            <input
              type="number"
              value={form.times_flown}
              onChange={e => set('times_flown', e.target.value)}
              className="w-20 bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
              min="1"
            />
          </div>
        )}
      </div>

      <div>
        <label className={labelClass}>Notes</label>
        <textarea
          value={form.notes}
          onChange={e => set('notes', e.target.value)}
          rows={3}
          className={`${inputClass} resize-y`}
        />
      </div>

      <div className="flex gap-2 pt-2">
        <button
          onClick={() => onSubmit(form)}
          disabled={!form.date || !form.dep_airport.trim() || !form.arr_airport.trim()}
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
