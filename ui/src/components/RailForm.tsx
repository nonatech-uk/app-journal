import { useState, useEffect } from 'react'

interface RailFormData {
  date: string
  time: string
  from_station: string
  from_code: string
  to_station: string
  to_code: string
  operator: string
  ticket_type: string
  direction: string
  train: string
  via: string
  reference: string
  price: string
  currency: string
}

interface Props {
  initial?: Partial<RailFormData>
  onSubmit: (data: RailFormData) => void
  onCancel: () => void
  submitLabel?: string
}

export default function RailForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [form, setForm] = useState<RailFormData>({
    date: new Date().toISOString().slice(0, 10),
    time: '',
    from_station: '',
    from_code: '',
    to_station: '',
    to_code: '',
    operator: '',
    ticket_type: '',
    direction: '',
    train: '',
    via: '',
    reference: '',
    price: '',
    currency: 'GBP',
    ...initial,
  })

  useEffect(() => {
    if (initial) setForm(prev => ({ ...prev, ...initial }))
  }, [initial])

  const set = (field: keyof RailFormData, value: string) =>
    setForm(prev => ({ ...prev, [field]: value }))

  const inputCls = 'w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50'
  const labelCls = 'block text-xs text-text-secondary mb-1'

  return (
    <div className="space-y-3">
      {/* Row 1: Date | Time */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Date *</label>
          <input
            type="date"
            value={form.date}
            onChange={e => set('date', e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Time</label>
          <input
            type="time"
            value={form.time}
            onChange={e => set('time', e.target.value)}
            className={inputCls}
          />
        </div>
      </div>

      {/* Row 2: From Station | Station Code */}
      <div className="grid grid-cols-[1fr_8rem] gap-3">
        <div>
          <label className={labelCls}>From Station *</label>
          <input
            type="text"
            value={form.from_station}
            onChange={e => set('from_station', e.target.value)}
            className={inputCls}
            autoFocus
          />
        </div>
        <div>
          <label className={labelCls}>Station Code</label>
          <input
            type="text"
            value={form.from_code}
            onChange={e => set('from_code', e.target.value)}
            className={inputCls}
          />
        </div>
      </div>

      {/* Row 3: To Station | Station Code */}
      <div className="grid grid-cols-[1fr_8rem] gap-3">
        <div>
          <label className={labelCls}>To Station *</label>
          <input
            type="text"
            value={form.to_station}
            onChange={e => set('to_station', e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Station Code</label>
          <input
            type="text"
            value={form.to_code}
            onChange={e => set('to_code', e.target.value)}
            className={inputCls}
          />
        </div>
      </div>

      {/* Row 4: Operator | Train */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Operator</label>
          <input
            type="text"
            value={form.operator}
            onChange={e => set('operator', e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Train</label>
          <input
            type="text"
            value={form.train}
            onChange={e => set('train', e.target.value)}
            className={inputCls}
          />
        </div>
      </div>

      {/* Row 5: Ticket Type | Direction */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Ticket Type</label>
          <input
            type="text"
            value={form.ticket_type}
            onChange={e => set('ticket_type', e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Direction</label>
          <input
            type="text"
            value={form.direction}
            onChange={e => set('direction', e.target.value)}
            className={inputCls}
          />
        </div>
      </div>

      {/* Row 6: Price | Currency */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Price</label>
          <input
            type="number"
            step="0.01"
            value={form.price}
            onChange={e => set('price', e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Currency</label>
          <select
            value={form.currency}
            onChange={e => set('currency', e.target.value)}
            className={inputCls}
          >
            <option value="GBP">GBP</option>
            <option value="EUR">EUR</option>
            <option value="USD">USD</option>
            <option value="CHF">CHF</option>
          </select>
        </div>
      </div>

      {/* Row 7: Via (full width) */}
      <div>
        <label className={labelCls}>Via</label>
        <input
          type="text"
          value={form.via}
          onChange={e => set('via', e.target.value)}
          className={inputCls}
        />
      </div>

      {/* Row 8: Reference (full width) */}
      <div>
        <label className={labelCls}>Reference</label>
        <input
          type="text"
          value={form.reference}
          onChange={e => set('reference', e.target.value)}
          className={inputCls}
        />
      </div>

      {/* Buttons */}
      <div className="flex gap-2 pt-2">
        <button
          onClick={() => onSubmit(form)}
          disabled={!form.date || !form.from_station.trim() || !form.to_station.trim()}
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
