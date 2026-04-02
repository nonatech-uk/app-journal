import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface EventType {
  id: number
  name: string
  event_count: number
}

function fetchEventTypes(): Promise<EventType[]> {
  return apiFetch<EventType[]>('/event-types')
}

export default function EventTypes() {
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const { data: types, isLoading } = useQuery({
    queryKey: ['event-types'],
    queryFn: fetchEventTypes,
  })

  const create = useMutation({
    mutationFn: (name: string) =>
      apiFetch('/event-types', { method: 'POST', body: JSON.stringify({ name }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event-types'] })
      setNewName('')
    },
  })

  const update = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      apiFetch(`/event-types/${id}`, { method: 'PUT', body: JSON.stringify({ name }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event-types'] })
      setEditingId(null)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/event-types/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event-types'] })
      setConfirmDeleteId(null)
    },
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading event types...</div>

  const items = types ?? []

  return (
    <div className="p-6 max-w-2xl">
      <h2 className="text-xl font-bold text-text-primary mb-4">Event Types</h2>

      {/* Add new type */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && newName.trim()) create.mutate(newName)
          }}
          placeholder="New event type..."
          className="flex-1 bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
        />
        <button
          onClick={() => create.mutate(newName)}
          disabled={!newName.trim() || create.isPending}
          className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          Add
        </button>
      </div>
      {create.isError && (
        <div className="text-xs text-red-600 mb-3">
          Failed: {(create.error as Error).message}
        </div>
      )}

      {/* Types table */}
      <div className="bg-bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-bg-secondary">
              <th className="text-left px-3 py-2 text-xs text-text-secondary font-medium">Name</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium">Events</th>
              <th className="text-right px-3 py-2 text-xs text-text-secondary font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {items.map(t => (
              <tr key={t.id} className="border-b border-border last:border-0 hover:bg-bg-hover">
                <td className="px-3 py-2">
                  {editingId === t.id ? (
                    <div className="flex gap-1.5">
                      <input
                        type="text"
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter' && editName.trim()) update.mutate({ id: t.id, name: editName })
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        className="flex-1 bg-bg-secondary border border-border rounded px-2 py-0.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                        autoFocus
                      />
                      <button
                        onClick={() => update.mutate({ id: t.id, name: editName })}
                        disabled={!editName.trim()}
                        className="text-xs text-accent hover:underline"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="text-xs text-text-secondary hover:text-text-primary"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => { setEditingId(t.id); setEditName(t.name) }}
                      className="text-text-primary font-medium hover:text-accent transition-colors"
                      title="Click to rename"
                    >
                      {t.name.charAt(0).toUpperCase() + t.name.slice(1)}
                    </button>
                  )}
                </td>
                <td className="px-3 py-2 text-right text-text-secondary">{t.event_count}</td>
                <td className="px-3 py-2 text-right">
                  {t.event_count === 0 ? (
                    confirmDeleteId === t.id ? (
                      <span className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => remove.mutate(t.id)}
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
                        onClick={() => setConfirmDeleteId(t.id)}
                        className="text-xs text-red-500 hover:text-red-700"
                      >
                        Delete
                      </button>
                    )
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <div className="text-center text-text-secondary py-8">No event types defined</div>
        )}
      </div>

      {update.isError && (
        <div className="text-xs text-red-600 mt-3">
          Rename failed: {(update.error as Error).message}
        </div>
      )}
    </div>
  )
}
