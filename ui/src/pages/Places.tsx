import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPlaces, fetchPlaceTypes, createPlace, deletePlace, syncPlaces } from '../api/places'

export default function Places() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [syncResult, setSyncResult] = useState<Record<string, number> | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['places'], queryFn: fetchPlaces })
  const { data: placeTypes } = useQuery({ queryKey: ['place-types'], queryFn: fetchPlaceTypes })

  const [form, setForm] = useState({
    name: '', place_type_id: 1, latitude: '', longitude: '',
    distance_m: '200', date_from: '', date_to: '', notes: '',
  })

  const create = useMutation({
    mutationFn: () => createPlace({
      name: form.name,
      place_type_id: form.place_type_id,
      latitude: parseFloat(form.latitude),
      longitude: parseFloat(form.longitude),
      distance_m: parseInt(form.distance_m) || 200,
      date_from: form.date_from || null,
      date_to: form.date_to || null,
      notes: form.notes || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['places'] })
      setShowCreate(false)
      setForm({ name: '', place_type_id: 1, latitude: '', longitude: '', distance_m: '200', date_from: '', date_to: '', notes: '' })
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => deletePlace(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['places'] })
      setConfirmDeleteId(null)
    },
  })

  const sync = useMutation({
    mutationFn: syncPlaces,
    onSuccess: (result) => {
      setSyncResult(result)
      queryClient.invalidateQueries({ queryKey: ['places'] })
    },
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading places...</div>

  const places = data?.items ?? []
  const types = placeTypes ?? []
  const set = (field: string, value: string | number) => setForm(prev => ({ ...prev, [field]: value }))

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">Places — {data?.total ?? 0}</h2>
        <div className="flex gap-2">
          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-primary hover:bg-bg-hover border border-border transition-colors disabled:opacity-50"
          >
            {sync.isPending ? 'Syncing...' : 'Sync'}
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent-hover transition-colors"
          >
            {showCreate ? 'Cancel' : '+ Add Place'}
          </button>
        </div>
      </div>

      {syncResult && (
        <div className="bg-bg-card border border-border rounded-lg p-3 mb-4 text-xs text-text-secondary">
          Sync: {syncResult.matched} locations matched, {syncResult.events_matched} events matched,
          {' '}{syncResult.cleared + syncResult.events_cleared} cleared.
          <button onClick={() => setSyncResult(null)} className="ml-2 text-accent hover:underline">dismiss</button>
        </div>
      )}

      {showCreate && (
        <div className="bg-bg-card border border-border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-medium text-text-primary mb-3">New Place</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-text-secondary mb-1">Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => set('name', e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">Type</label>
                <select
                  value={form.place_type_id}
                  onChange={e => set('place_type_id', Number(e.target.value))}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                >
                  {types.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-text-secondary mb-1">Latitude *</label>
                <input
                  type="number" step="any"
                  value={form.latitude}
                  onChange={e => set('latitude', e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                  placeholder="51.5074"
                />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">Longitude *</label>
                <input
                  type="number" step="any"
                  value={form.longitude}
                  onChange={e => set('longitude', e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                  placeholder="-0.1278"
                />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">Radius (m)</label>
                <input
                  type="number"
                  value={form.distance_m}
                  onChange={e => set('distance_m', e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-text-secondary mb-1">Active from</label>
                <input
                  type="date"
                  value={form.date_from}
                  onChange={e => set('date_from', e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">Active to</label>
                <input
                  type="date"
                  value={form.date_to}
                  onChange={e => set('date_to', e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Notes</label>
              <input
                type="text"
                value={form.notes}
                onChange={e => set('notes', e.target.value)}
                className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => create.mutate()}
                disabled={!form.name.trim() || !form.latitude || !form.longitude}
                className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
              >
                Create
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-hover border border-border transition-colors"
              >
                Cancel
              </button>
            </div>
            {create.isError && (
              <div className="text-xs text-red-600">Failed: {(create.error as Error).message}</div>
            )}
          </div>
        </div>
      )}

      {/* Places table */}
      <div className="bg-bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-bg-secondary">
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Name</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Type</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Location</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Radius</th>
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Active</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {places.map(p => (
              <tr key={p.id} className="border-b border-border last:border-0 hover:bg-bg-hover">
                <td className="px-3 py-2 text-text-primary font-medium">{p.name}</td>
                <td className="px-3 py-2 text-text-secondary">{p.place_type}</td>
                <td className="px-3 py-2">
                  <a
                    href={`https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=16/${p.lat}/${p.lon}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:underline"
                  >
                    {p.lat.toFixed(4)}, {p.lon.toFixed(4)}
                  </a>
                </td>
                <td className="px-3 py-2 text-text-secondary">{p.distance_m}m</td>
                <td className="px-3 py-2 text-text-secondary text-xs">
                  {p.date_from || p.date_to
                    ? `${p.date_from ?? '...'} — ${p.date_to ?? '...'}`
                    : 'Always'}
                </td>
                <td className="px-3 py-2 text-right">
                  {confirmDeleteId === p.id ? (
                    <span className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => remove.mutate(p.id)}
                        className="text-xs text-red-600 hover:text-red-800"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="text-xs text-text-secondary hover:text-text-primary"
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <button
                      onClick={() => setConfirmDeleteId(p.id)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {places.length === 0 && (
          <div className="text-center text-text-secondary py-8">No places defined</div>
        )}
      </div>
    </div>
  )
}
