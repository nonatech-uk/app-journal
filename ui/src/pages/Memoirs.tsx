import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchMemoirs, createMemoir } from '../api/memoirs.ts'

export default function Memoirs() {
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['memoirs'],
    queryFn: fetchMemoirs,
  })

  const create = useMutation({
    mutationFn: createMemoir,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['memoirs'] })
      setShowCreate(false)
      navigate(`/memoir/${result.id}?edit=1`)
    },
  })

  const [title, setTitle] = useState('')
  const [dateLabel, setDateLabel] = useState('')
  const [description, setDescription] = useState('')
  const [startYear, setStartYear] = useState('')
  const [endYear, setEndYear] = useState('')

  const handleCreate = () => {
    if (!title.trim()) return
    create.mutate({
      title: title.trim(),
      date_label: dateLabel || null,
      description: description || null,
      start_year: startYear ? parseInt(startYear) : null,
      end_year: endYear ? parseInt(endYear) : null,
    })
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-text-primary">Memoirs</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-accent text-white rounded-lg text-sm hover:bg-accent-hover"
        >
          {showCreate ? 'Cancel' : 'New Memoir'}
        </button>
      </div>

      {showCreate && (
        <div className="bg-bg-card border border-border rounded-lg p-5 mb-6 space-y-3">
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Title (e.g. The Playhouse Years)"
            className="w-full bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary"
            autoFocus
          />
          <div className="grid grid-cols-3 gap-3">
            <input
              value={startYear}
              onChange={e => setStartYear(e.target.value)}
              placeholder="Start year"
              type="number"
              className="bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary"
            />
            <input
              value={endYear}
              onChange={e => setEndYear(e.target.value)}
              placeholder="End year"
              type="number"
              className="bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary"
            />
            <input
              value={dateLabel}
              onChange={e => setDateLabel(e.target.value)}
              placeholder="Date label (e.g. mid-1990s)"
              className="bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary"
            />
          </div>
          <input
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Short description"
            className="w-full bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary"
          />
          <button
            onClick={handleCreate}
            disabled={!title.trim() || create.isPending}
            className="px-4 py-2 bg-accent text-white rounded text-sm hover:bg-accent-hover disabled:opacity-50"
          >
            {create.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-text-secondary text-sm">Loading...</div>
      ) : (
        <div className="space-y-3">
          {(data?.items ?? []).map(memoir => (
            <div
              key={memoir.id}
              onClick={() => navigate(`/memoir/${memoir.id}`)}
              className="bg-bg-card border border-border rounded-lg p-5 hover:border-accent/30 transition-colors cursor-pointer"
            >
              <div className="flex items-start gap-4">
                <div className="flex-1">
                  <h2 className="text-base font-semibold text-text-primary mb-1">{memoir.title}</h2>
                  <div className="flex items-center gap-3 text-xs text-text-secondary mb-2">
                    {memoir.date_label && (
                      <span className="bg-accent/10 text-accent px-2 py-0.5 rounded">{memoir.date_label}</span>
                    )}
                    {!memoir.date_label && memoir.start_year && (
                      <span className="bg-accent/10 text-accent px-2 py-0.5 rounded">
                        {memoir.start_year}{memoir.end_year && memoir.end_year !== memoir.start_year ? `–${memoir.end_year}` : ''}
                      </span>
                    )}
                    {memoir.child_count > 0 && (
                      <span>{memoir.child_count} sub-page{memoir.child_count !== 1 ? 's' : ''}</span>
                    )}
                    {memoir.attachment_count > 0 && (
                      <span>{memoir.attachment_count} photo{memoir.attachment_count !== 1 ? 's' : ''}</span>
                    )}
                  </div>
                  {memoir.description && (
                    <p className="text-sm text-text-secondary">{memoir.description}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
          {(data?.items ?? []).length === 0 && (
            <div className="text-center py-12 text-text-secondary text-sm">
              No memoirs yet. Create your first memoir to start recording your life story.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
