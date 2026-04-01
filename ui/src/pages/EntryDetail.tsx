import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Markdown from 'react-markdown'
import { useEntry, useEnrichment } from '../hooks/useEntry'
import { useAuth } from '../hooks/useAuth'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toggleStar, updateEntry, deleteEntry, uploadVoiceNote, attachImmichPhotos, linkFlight, unlinkFlight, linkSkiingDay, importAllScrobbles, importAllWatches, fetchEntryPeople, searchPeople, linkPerson, unlinkPerson, createPerson, deleteAttachment, uploadAttachment } from '../api/entries'
import type { PersonSummary } from '../api/entries'
import VoiceRecorder from '../components/VoiceRecorder'
import ImmichBrowser from '../components/ImmichBrowser'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function EntryDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const entryId = id ? Number(id) : undefined
  const { data: entry, isLoading, refetch: refetchEntry } = useEntry(entryId)
  const { data: enrichment } = useEnrichment(entryId)

  // Refetch entry when returning from another tab (e.g. places editor)
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible' && entryId) {
        refetchEntry()
      }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [entryId, refetchEntry])

  // Keyboard navigation: left/right arrow for prev/next entry
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return
      if (e.key === 'ArrowLeft' && entry?.prev_entry_id) {
        navigate(`/entry/${entry.prev_entry_id}`)
      } else if (e.key === 'ArrowRight' && entry?.next_entry_id) {
        navigate(`/entry/${entry.next_entry_id}`)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [entry?.prev_entry_id, entry?.next_entry_id, navigate])
  const { data: user } = useAuth()
  const queryClient = useQueryClient()
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [editTags, setEditTags] = useState('')
  const [editRetrospective, setEditRetrospective] = useState('')
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(null)
  const [immichIds, setImmichIds] = useState<string[]>([])
  const [showImmich, setShowImmich] = useState(false)
  const [entryPeople, setEntryPeople] = useState<PersonSummary[]>([])
  const [personQuery, setPersonQuery] = useState('')
  const [personResults, setPersonResults] = useState<PersonSummary[]>([])
  const [showPersonSearch, setShowPersonSearch] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState<string | null>(null)

  const isAdmin = user?.role === 'admin'

  const closeLightbox = useCallback(() => setLightboxUrl(null), [])

  // Load people for this entry
  useEffect(() => {
    if (entryId) {
      fetchEntryPeople(entryId).then(setEntryPeople).catch(() => {})
    }
  }, [entryId])

  // Search people debounced
  useEffect(() => {
    if (personQuery.length < 2) { setPersonResults([]); return }
    const t = setTimeout(() => {
      searchPeople(personQuery).then(setPersonResults).catch(() => {})
    }, 200)
    return () => clearTimeout(t)
  }, [personQuery])
  useEffect(() => {
    if (!lightboxUrl) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeLightbox() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [lightboxUrl, closeLightbox])

  const starMutation = useMutation({
    mutationFn: () => toggleStar(entryId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      let result = await updateEntry(entryId!, {
        markdown_text: editText,
        tags: editTags.split(',').map(t => t.trim()).filter(Boolean),
        retrospective: editRetrospective,
      })
      if (immichIds.length > 0) {
        result = await attachImmichPhotos(entryId!, immichIds)
      }
      if (voiceBlob) {
        result = await uploadVoiceNote(entryId!, voiceBlob)
      }
      return result
    },
    onSuccess: () => {
      setEditing(false)
      setVoiceBlob(null)
      setImmichIds([])
      setShowImmich(false)
      queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteEntry(entryId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      navigate(-1)
    },
  })

  if (isLoading) return <div className="text-text-secondary">Loading...</div>
  if (!entry) return <div className="text-text-secondary">Entry not found</div>

  const cleanMarkdown = (text: string) =>
    text
      .replace(/!\[.*?\]\(dayone-moment:\/\/[^)]+\)/g, '')  // strip Day One moment refs
      .replace(/\\([!\-().#>])/g, '$1')  // strip Day One escape backslashes
      .trim()

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center gap-3 mb-1">
          <button
            onClick={() => entry.prev_entry_id && navigate(`/entry/${entry.prev_entry_id}`)}
            disabled={!entry.prev_entry_id}
            className="text-text-secondary hover:text-accent disabled:opacity-20 disabled:cursor-default transition-colors text-sm"
            title="Previous entry"
          >
            ←
          </button>
          <span className="text-sm text-text-secondary">{formatDate(entry.created_at)}</span>
          <button
            onClick={() => entry.next_entry_id && navigate(`/entry/${entry.next_entry_id}`)}
            disabled={!entry.next_entry_id}
            className="text-text-secondary hover:text-accent disabled:opacity-20 disabled:cursor-default transition-colors text-sm"
            title="Next entry"
          >
            →
          </button>
          {entry.journal_name && (
            <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent">{entry.journal_name}</span>
          )}
          <button
            onClick={() => starMutation.mutate()}
            className={`text-lg ${entry.starred ? 'text-warning' : 'text-text-secondary hover:text-warning'} transition-colors`}
          >
            {entry.starred ? '★' : '☆'}
          </button>
          {isAdmin && !editing && (
            <>
              <button
                onClick={() => { setEditText(entry.markdown_text || ''); setEditTags(entry.tags.join(', ')); setEditRetrospective(entry.retrospective || ''); setEditing(true) }}
                className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
              >
                Edit
              </button>
              <button
                onClick={() => { if (window.confirm('Delete this entry?')) deleteMutation.mutate() }}
                className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:text-red-400 hover:border-red-400/30 transition-colors"
              >
                Delete
              </button>
            </>
          )}
        </div>
        {entry.timezone && (
          <span className="text-xs text-text-secondary">{entry.timezone}</span>
        )}
        {entry.tags.length > 0 && (
          <div className="flex gap-1 mt-1 flex-wrap">
            {entry.tags.map((t) => (
              <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-bg-hover text-text-secondary">{t}</span>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Photos/Videos */}
          {(entry.attachments.length > 0 || editing) && (
            <div className="mb-4">
              <div className={`grid gap-2 ${entry.attachments.length === 1 ? 'max-w-sm' : 'grid-cols-2 lg:grid-cols-3'}`}>
                {entry.attachments.map((att) => (
                  <div key={att.id} className="rounded-lg overflow-hidden bg-bg-hover relative">
                    {att.type === 'mov' || att.type === 'mp4' ? (
                      <video
                        src={att.media_url!}
                        controls
                        className="w-full"
                        preload="metadata"
                      />
                    ) : att.type === 'audio' ? (
                      <div className="flex items-center gap-2 p-3">
                        <span className="text-text-secondary text-sm shrink-0">Voice note</span>
                        <audio src={att.media_url!} controls className="w-full h-8" />
                      </div>
                    ) : att.type === 'pdf' ? (
                      <a href={att.media_url!} target="_blank" rel="noreferrer"
                         className="flex items-center justify-center h-24 text-accent text-sm">
                        PDF: {att.filename || 'document.pdf'}
                      </a>
                    ) : (
                      <a
                        href={att.immich_url || undefined}
                        target={att.immich_url ? '_blank' : undefined}
                        rel={att.immich_url ? 'noreferrer' : undefined}
                        onClick={att.immich_url ? undefined : () => setLightboxUrl(att.media_url!)}
                      >
                        <img
                          src={`${att.media_url}?thumb=1`}
                          alt={att.caption || ''}
                          className="w-full h-auto max-h-64 object-cover cursor-pointer"
                          loading="lazy"
                        />
                      </a>
                    )}
                    {att.caption && (
                      <p className="text-xs text-text-secondary p-1">{att.caption}</p>
                    )}
                    {editing && (
                      <button
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center hover:bg-red-600"
                        onClick={async (e) => {
                          e.stopPropagation()
                          if (!entryId) return
                          await deleteAttachment(entryId, att.id)
                          queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
                        }}
                      >
                        x
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {editing && (
                <div
                  className={`mt-2 border-2 border-dashed rounded-lg p-4 text-center text-sm transition-colors cursor-pointer ${
                    dragOver
                      ? 'border-accent bg-accent/5 text-accent'
                      : 'border-border text-text-secondary hover:border-accent/50'
                  }`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                  onDragEnter={(e) => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={async (e) => {
                    e.preventDefault()
                    setDragOver(false)
                    if (!entryId) return
                    const files = Array.from(e.dataTransfer.files)
                    for (let i = 0; i < files.length; i++) {
                      setUploading(`Uploading ${i + 1} of ${files.length}...`)
                      await uploadAttachment(entryId, files[i])
                    }
                    setUploading(null)
                    queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
                  }}
                  onClick={() => {
                    const input = document.createElement('input')
                    input.type = 'file'
                    input.multiple = true
                    input.onchange = async () => {
                      if (!input.files || !entryId) return
                      const files = Array.from(input.files)
                      for (let i = 0; i < files.length; i++) {
                        setUploading(`Uploading ${i + 1} of ${files.length}...`)
                        await uploadAttachment(entryId, files[i])
                      }
                      setUploading(null)
                      queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
                    }
                    input.click()
                  }}
                >
                  {uploading || 'Drop files here or click to upload'}
                </div>
              )}
            </div>
          )}

          {/* Text */}
          {editing ? (
            <div className="space-y-3">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full h-64 bg-bg-secondary border border-border rounded-lg p-3 text-text-primary text-sm font-mono resize-y focus:outline-none focus:border-accent/50"
              />
              <div>
                <label className="text-xs text-text-secondary block mb-1">Tags (comma-separated)</label>
                <input
                  value={editTags}
                  onChange={(e) => setEditTags(e.target.value)}
                  className="w-full bg-bg-secondary border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                />
              </div>
              <div>
                <label className="text-xs text-text-secondary block mb-1">Retrospective</label>
                <textarea
                  value={editRetrospective}
                  onChange={(e) => setEditRetrospective(e.target.value)}
                  placeholder="Looking back on this..."
                  className="w-full h-32 bg-bg-secondary border border-border rounded-lg p-3 text-text-primary text-sm resize-y focus:outline-none focus:border-accent/50"
                />
              </div>
              <div>
                <button
                  type="button"
                  onClick={() => setShowImmich(!showImmich)}
                  className="text-sm text-text-secondary hover:text-accent transition-colors mb-2"
                >
                  {showImmich ? 'Hide photos' : 'Attach photos from library'}
                  {immichIds.length > 0 && ` (${immichIds.length} selected)`}
                </button>
                {showImmich && (
                  <ImmichBrowser
                    selectedIds={immichIds}
                    onSelectionChange={setImmichIds}
                  />
                )}
              </div>
              <VoiceRecorder
                onRecorded={setVoiceBlob}
                onClear={() => setVoiceBlob(null)}
                hasRecording={!!voiceBlob}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                  className="text-sm px-3 py-1.5 rounded bg-accent text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
                >
                  {saveMutation.isPending ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => { setEditing(false); setVoiceBlob(null); setImmichIds([]); setShowImmich(false) }}
                  className="text-sm px-3 py-1.5 rounded border border-border text-text-secondary hover:text-text-primary transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : entry.markdown_text ? (
            <div className="max-w-none text-text-primary leading-relaxed space-y-2">
            <Markdown
              components={{
                h1: ({ children }) => <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-xl font-semibold mt-3 mb-2">{children}</h2>,
                h3: ({ children }) => <h3 className="text-lg font-semibold mt-2 mb-1">{children}</h3>,
                p: ({ children }) => <p className="mb-2">{children}</p>,
                ul: ({ children }) => <ul className="list-disc pl-5 mb-2">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-5 mb-2">{children}</ol>,
                li: ({ children }) => <li className="mb-0.5">{children}</li>,
                a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">{children}</a>,
                blockquote: ({ children }) => <blockquote className="border-l-2 border-accent/30 pl-3 italic text-text-secondary">{children}</blockquote>,
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                code: ({ children }) => <code className="bg-bg-hover px-1 py-0.5 rounded text-sm">{children}</code>,
                hr: () => <hr className="border-border my-4" />,
              }}
            >
              {cleanMarkdown(entry.markdown_text)}
            </Markdown>
            </div>
          ) : null}

          {/* Retrospective */}
          {!editing && entry.retrospective && (
            <div className="mt-6 border-l-2 border-accent/30 pl-4">
              <div className="flex items-baseline gap-2 mb-1">
                <h4 className="text-sm font-medium text-accent">Retrospective</h4>
                {entry.retrospective_at && (
                  <span className="text-xs text-text-secondary">
                    {new Date(entry.retrospective_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </span>
                )}
              </div>
              <div className="max-w-none text-text-primary leading-relaxed space-y-2">
                <Markdown
                  components={{
                    p: ({ children }) => <p className="mb-2">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">{children}</a>,
                  }}
                >
                  {entry.retrospective}
                </Markdown>
              </div>
            </div>
          )}

          {/* Device info */}
          {entry.device_name && (
            <div className="mt-4 text-xs text-text-secondary">
              {entry.device_name} {entry.device_model ? `(${entry.device_model})` : ''}
            </div>
          )}
        </div>

        {/* Sidebar — context */}
        <div className="w-64 shrink-0 space-y-4">
          {/* Mood & Energy */}
          <div className="bg-bg-card border border-border rounded-lg p-3">
            <div className="flex items-center justify-between">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-secondary w-12">Mood</span>
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map(v => (
                      <button
                        key={v}
                        className={`w-5 h-5 rounded text-xs ${
                          entry.mood && v <= entry.mood
                            ? 'bg-accent text-white'
                            : 'bg-bg-secondary text-text-secondary hover:bg-accent/20'
                        }`}
                        onClick={async () => {
                          if (!entryId || user?.role !== 'admin') return
                          const newVal = entry.mood === v ? 0 : v
                          await updateEntry(entryId, { mood: newVal })
                          queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
                        }}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-secondary w-12">Energy</span>
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map(v => (
                      <button
                        key={v}
                        className={`w-5 h-5 rounded text-xs ${
                          entry.energy && v <= entry.energy
                            ? 'bg-green-500 text-white'
                            : 'bg-bg-secondary text-text-secondary hover:bg-green-500/20'
                        }`}
                        onClick={async () => {
                          if (!entryId || user?.role !== 'admin') return
                          const newVal = entry.energy === v ? 0 : v
                          await updateEntry(entryId, { energy: newVal })
                          queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
                        }}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* People */}
          <div className="bg-bg-card border border-border rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <h4 className="text-xs font-medium text-text-secondary">People</h4>
              {isAdmin && (
                <button
                  className="text-xs text-text-secondary hover:text-accent"
                  onClick={() => setShowPersonSearch(!showPersonSearch)}
                >
                  {showPersonSearch ? 'Done' : '+ Add'}
                </button>
              )}
            </div>
            {entryPeople.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-1">
                {entryPeople.map(p => (
                  <span key={p.id} className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-bg-secondary text-text-primary">
                    {p.nickname || p.name}
                    {p.role && <span className="text-text-secondary">({p.role})</span>}
                    {isAdmin && (
                      <button
                        className="text-text-secondary hover:text-red-400 ml-0.5"
                        onClick={async () => {
                          if (!entryId) return
                          await unlinkPerson(entryId, p.id)
                          setEntryPeople(prev => prev.filter(x => x.id !== p.id))
                        }}
                      >
                        x
                      </button>
                    )}
                  </span>
                ))}
              </div>
            )}
            {entryPeople.length === 0 && !showPersonSearch && (
              <div className="text-xs text-text-secondary italic">No people tagged</div>
            )}
            {showPersonSearch && (
              <div className="mt-1">
                <input
                  type="text"
                  className="w-full text-xs px-2 py-1 rounded border border-border bg-bg-primary text-text-primary"
                  placeholder="Search or create..."
                  value={personQuery}
                  onChange={e => setPersonQuery(e.target.value)}
                  autoFocus
                />
                {personResults.length > 0 && (
                  <div className="mt-1 space-y-0.5 max-h-32 overflow-auto">
                    {personResults
                      .filter(p => !entryPeople.some(ep => ep.id === p.id))
                      .map(p => (
                        <button
                          key={p.id}
                          className="block w-full text-left text-xs px-2 py-1 rounded hover:bg-bg-hover text-text-primary"
                          onClick={async () => {
                            if (!entryId) return
                            await linkPerson(entryId, p.id)
                            setEntryPeople(prev => [...prev, p])
                            setPersonQuery('')
                            setPersonResults([])
                          }}
                        >
                          {p.name} {p.nickname && <span className="text-text-secondary">({p.nickname})</span>}
                        </button>
                      ))}
                  </div>
                )}
                {personQuery.length >= 2 && personResults.length === 0 && (
                  <button
                    className="mt-1 text-xs text-accent hover:underline"
                    onClick={async () => {
                      if (!entryId) return
                      const { id } = await createPerson(personQuery)
                      await linkPerson(entryId, id)
                      setEntryPeople(prev => [...prev, { id, name: personQuery, nickname: null }])
                      setPersonQuery('')
                    }}
                  >
                    Create "{personQuery}"
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Location(s) + Weather */}
          {(entry.locations?.length > 0 || entry.location) && (() => {
            const locs = entry.locations?.length > 0 ? entry.locations : entry.location ? [entry.location] : []
            if (locs.length === 0) return null
            const multi = locs.length > 1
            const labels = multi ? ['Start', 'End'] : [null]
            const placesUrl = (loc: typeof locs[0]) =>
              loc.latitude != null && loc.longitude != null
                ? `https://locations.mees.st/places?lat=${loc.latitude}&lon=${loc.longitude}&name=${encodeURIComponent(loc.place_name || '')}&dt=${entry.created_at?.slice(0, 10) || ''}`
                : null
            const displayName = (loc: typeof locs[0]) =>
              loc.place_label ? `${loc.place_label} (${loc.place_name})` : loc.place_name
            return (
              <div className="bg-bg-card border border-border rounded-lg p-3">
                <h4 className="text-xs font-medium text-text-secondary mb-1">
                  {multi ? 'Locations' : 'Location'}
                </h4>
                <div className="space-y-1.5">
                  {locs.map((loc, i) => {
                    const url = placesUrl(loc)
                    return (
                      <div key={i}>
                        <div className="text-sm">
                          {labels[i] && <span className="text-text-secondary text-xs mr-1.5">{labels[i]}:</span>}
                          {url ? (
                            <a href={url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                              {displayName(loc)}
                            </a>
                          ) : (
                            displayName(loc)
                          )}
                        </div>
                        {loc.locality && (
                          <div className="text-xs text-text-secondary">
                            {loc.locality}
                            {loc.admin_area ? `, ${loc.admin_area}` : ''}
                            {loc.country ? `, ${loc.country}` : ''}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })()}

          {/* Weather */}
          {(() => {
            const allWeathers = entry.weathers?.length > 0 ? entry.weathers : entry.weather ? [entry.weather] : []
            if (allWeathers.length === 0) return null
            // If there are location-linked weathers, only show those (skip legacy standalone)
            const locationLinked = allWeathers.filter(w => w.location_id != null)
            const weathers = locationLinked.length > 0 ? locationLinked : allWeathers
            const locs = entry.locations?.length > 0 ? entry.locations : entry.location ? [entry.location] : []
            const multi = weathers.length > 1 && locs.length > 1
            const labels = multi ? ['Start', 'End'] : [null]

            const renderWeather = (w: typeof entry.weather, label?: string | null) => (
              <div>
                <div className="text-sm">
                  {label && <span className="text-text-secondary text-xs mr-1.5">{label}:</span>}
                  {w!.temp_celsius !== null && `${Math.round(w!.temp_celsius!)}°C`}
                  {w!.conditions && ` — ${w!.conditions}`}
                </div>
                {w!.relative_humidity !== null && (
                  <div className="text-xs text-text-secondary">
                    Humidity: {w!.relative_humidity}%
                    {w!.wind_speed_kph !== null && ` | Wind: ${Math.round(w!.wind_speed_kph!)} kph`}
                  </div>
                )}
                {w!.wind_speed_kph !== null && w!.relative_humidity === null && (
                  <div className="text-xs text-text-secondary">
                    Wind: {Math.round(w!.wind_speed_kph!)} kph
                  </div>
                )}
              </div>
            )

            return (
              <div className="bg-bg-card border border-border rounded-lg p-3">
                <h4 className="text-xs font-medium text-text-secondary mb-1">Weather</h4>
                <div className="space-y-1.5">
                  {weathers.map((w, i) => (
                    <div key={i}>{renderWeather(w, multi ? labels[i] ?? null : null)}</div>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* Music */}
          {entry.music_tracks && entry.music_tracks.length > 0 ? (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">
                Music ({entry.music_tracks.length})
              </h4>
              <div className="space-y-1.5 max-h-60 overflow-auto">
                {entry.music_tracks.map((t, i) => (
                  <div key={i} className="text-xs">
                    <div className="flex items-center gap-1">
                      {t.recording_mbid ? (
                        <a href={`https://musicbrainz.org/recording/${t.recording_mbid}`}
                           target="_blank" rel="noopener noreferrer"
                           className="text-accent hover:underline">{t.track}</a>
                      ) : <span className="text-text-primary">{t.track}</span>}
                      {t.spotify_track_id && (
                        <a href={`https://open.spotify.com/track/${t.spotify_track_id}`}
                           target="_blank" rel="noopener noreferrer"
                           className="text-green-500 hover:text-green-400 flex-shrink-0"
                           title="Open in Spotify">
                          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                          </svg>
                        </a>
                      )}
                    </div>
                    <div className="text-text-secondary">
                      {t.artist_mbid ? (
                        <a href={`https://musicbrainz.org/artist/${t.artist_mbid}`}
                           target="_blank" rel="noopener noreferrer"
                           className="hover:text-accent hover:underline">{t.artist}</a>
                      ) : t.artist}
                      {t.album && ` — ${t.album}`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : entry.music && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">Playing</h4>
              <div className="text-sm">{entry.music.track}</div>
              <div className="text-xs text-text-secondary">{entry.music.artist} — {entry.music.album}</div>
            </div>
          )}

          {/* Enrichment — Scrobbles (only show if there are unlinked ones to import) */}
          {enrichment?.scrobbles && enrichment.scrobbles.some(s => !s.linked) && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-xs font-medium text-text-secondary">
                  Unlinked Scrobbles ({enrichment.scrobbles.filter(s => !s.linked).length})
                </h4>
                {user?.role === 'admin' && (
                  <button
                    className="text-xs px-1.5 py-0.5 rounded bg-bg-secondary text-text-secondary hover:bg-accent/10 hover:text-accent"
                    onClick={async () => {
                      if (!entryId) return
                      await importAllScrobbles(entryId)
                      queryClient.invalidateQueries({ queryKey: ['enrichment', entryId] })
                      queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
                    }}
                  >
                    Import All
                  </button>
                )}
              </div>
              <div className="space-y-1 max-h-40 overflow-auto">
                {enrichment.scrobbles.filter(s => !s.linked).map((s) => (
                  <div key={s.id} className="text-xs flex items-center gap-1">
                    <span className="text-text-primary">{s.track}</span>
                    <span className="text-text-secondary"> — {s.artist}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Enrichment — Watches */}
          {enrichment?.watches && enrichment.watches.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-xs font-medium text-text-secondary">
                  Watched ({enrichment.watches.length})
                </h4>
                {user?.role === 'admin' && enrichment.watches.some(w => !w.linked) && (
                  <button
                    className="text-xs px-1.5 py-0.5 rounded bg-bg-secondary text-text-secondary hover:bg-accent/10 hover:text-accent"
                    onClick={async () => {
                      if (!entryId) return
                      await importAllWatches(entryId)
                      queryClient.invalidateQueries({ queryKey: ['enrichment', entryId] })
                    }}
                  >
                    Import All
                  </button>
                )}
              </div>
              <div className="space-y-1 max-h-40 overflow-auto">
                {enrichment.watches.map((w, i) => (
                  <div key={i} className="text-xs flex items-center gap-1">
                    {w.linked && <span className="text-accent text-[10px]">✓</span>}
                    <span className="text-text-secondary">{w.media_type === 'movie' ? '🎬' : '📺'}</span>
                    {w.rating_key ? (
                      <a href={`https://plex.mees.st/web/index.html#!/server/9e1fdd8bbe89e8e8266de847db0b0ee2d0137c5c/details?key=${encodeURIComponent('/library/metadata/' + w.rating_key)}`}
                         target="_blank" rel="noopener noreferrer"
                         className="text-text-primary hover:text-accent hover:underline">
                        {w.title}
                      </a>
                    ) : (
                      <span className="text-text-primary">{w.title}</span>
                    )}
                    {w.year && <span className="text-text-secondary">({w.year})</span>}
                    {w.percent_complete != null && w.percent_complete < 90 && (
                      <span className="text-text-secondary">{w.percent_complete}%</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Enrichment — Transactions */}
          {enrichment?.transactions && enrichment.transactions.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">
                Spending ({enrichment.transactions.length})
              </h4>
              <div className="space-y-1 max-h-40 overflow-auto">
                {enrichment.transactions.map((t, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-text-primary truncate">{t.merchant_name}</span>
                    <span className="text-expense shrink-0 ml-1">
                      {Math.abs(t.amount).toFixed(2)} {t.currency}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Enrichment — GPS Track */}
          {enrichment?.gps_track && enrichment.gps_track.point_count > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">GPS Track</h4>
              <div className="text-xs text-text-secondary mb-2">
                {enrichment.gps_track.point_count.toLocaleString()} GPS points
              </div>
              {enrichment.gps_track.track_svg_url && enrichment.gps_track.track_url && (
                <a href={enrichment.gps_track.track_url} target="_blank" rel="noopener noreferrer">
                  <img
                    src={enrichment.gps_track.track_svg_url}
                    alt="GPS track for the day"
                    className="w-full rounded border border-border hover:border-accent/50 transition-colors"
                    loading="lazy"
                  />
                </a>
              )}
            </div>
          )}

          {/* Enrichment — Skiing */}
          {enrichment?.skiing && enrichment.skiing.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">Skiing</h4>
              <div className="space-y-2">
                {enrichment.skiing.map((s) => (
                  <div key={s.id} className="text-xs">
                    <div className="flex items-center gap-1">
                      <span className="font-medium text-text-primary">{s.location}</span>
                      {s.season && <span className="text-text-secondary">({s.season})</span>}
                      {user?.role === 'admin' && (
                        <button
                          className={`ml-auto text-xs px-1.5 py-0.5 rounded ${
                            s.linked
                              ? 'bg-accent/20 text-accent'
                              : 'bg-bg-secondary text-text-secondary hover:bg-accent/10 hover:text-accent'
                          }`}
                          onClick={async () => {
                            if (!entryId || s.linked) return
                            await linkSkiingDay(entryId, s.id, s.location ?? undefined)
                            queryClient.invalidateQueries({ queryKey: ['enrichment', entryId] })
                          }}
                        >
                          {s.linked ? '✓' : 'Link'}
                        </button>
                      )}
                    </div>
                    <div className="text-text-secondary grid grid-cols-2 gap-x-2 mt-0.5">
                      {s.vertical_down_m && <span>↓ {s.vertical_down_m.toLocaleString()}m</span>}
                      {s.distance_km && <span>{s.distance_km} km</span>}
                      {s.num_runs && <span>{s.num_runs} runs</span>}
                      {s.max_speed_kmh && <span>{s.max_speed_kmh} km/h max</span>}
                      {s.max_altitude_m && <span>{s.max_altitude_m.toLocaleString()}m peak</span>}
                      {s.duration_hours && <span>{s.duration_hours}h</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Enrichment — Flights */}
          {enrichment?.flights && enrichment.flights.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">
                Flights ({enrichment.flights.length})
              </h4>
              <div className="space-y-2">
                {enrichment.flights.map((f) => (
                  <div key={f.id} className="text-xs">
                    <div className="flex items-center gap-1">
                      <span className="font-medium text-text-primary">
                        {f.dep_airport} → {f.arr_airport}
                      </span>
                      {f.flight_number && (
                        <span className="text-text-secondary">{f.flight_number}</span>
                      )}
                      {user?.role === 'admin' && (
                        <button
                          className={`ml-auto text-xs px-1.5 py-0.5 rounded ${
                            f.linked
                              ? 'bg-accent/20 text-accent'
                              : 'bg-bg-secondary text-text-secondary hover:bg-accent/10 hover:text-accent'
                          }`}
                          onClick={async () => {
                            if (!entryId) return
                            if (f.linked) {
                              await unlinkFlight(entryId, f.id)
                            } else {
                              await linkFlight(entryId, f.id)
                            }
                            queryClient.invalidateQueries({ queryKey: ['enrichment', entryId] })
                          }}
                        >
                          {f.linked ? '✓' : 'Link'}
                        </button>
                      )}
                    </div>
                    <div className="text-text-secondary">
                      {f.airline && <span>{f.airline}</span>}
                      {f.aircraft_type && <span> · {f.aircraft_type}</span>}
                      {f.dep_time && <span> · {f.dep_time.slice(0, 5)}</span>}
                      {f.distance_km && <span> · {f.distance_km} km</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={closeLightbox}
        >
          <img
            src={lightboxUrl}
            className="max-w-[90vw] max-h-[90vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  )
}
