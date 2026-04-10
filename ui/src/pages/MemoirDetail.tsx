import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchMemoir, updateMemoir, deleteMemoir, createMemoir, autoLinkEntries, publishMemoir, publishAll, unpublishMemoir, generateExcerpt } from '../api/memoirs.ts'
import { uploadVoiceNote, attachImmichPhotos, deleteAttachment, uploadAttachment } from '../api/entries'
import Markdown from 'react-markdown'
import VoiceRecorder from '../components/VoiceRecorder'
import ImmichBrowser from '../components/ImmichBrowser'

export default function MemoirDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [showAddChild, setShowAddChild] = useState(false)
  const [showImmich, setShowImmich] = useState(false)
  const [hasRecording, setHasRecording] = useState(false)
  const [immichIds, setImmichIds] = useState<string[]>([])
  const [localTags, setLocalTags] = useState<string | null>(null)
  const [localSlug, setLocalSlug] = useState<string | null>(null)
  const [localExcerpt, setLocalExcerpt] = useState<string | null>(null)
  const [publishOn, setPublishOn] = useState('')

  const { data: memoir, isLoading } = useQuery({
    queryKey: ['memoir', id],
    queryFn: () => fetchMemoir(Number(id)),
    enabled: !!id,
  })

  // Auto-enter edit mode when ?edit=1 is present (e.g. after creation)
  useEffect(() => {
    if (searchParams.get('edit') === '1' && memoir && !editing) {
      setEditTitle(memoir.title)
      setEditDateLabel(memoir.date_label ?? '')
      setEditDescription(memoir.description ?? '')
      setEditMarkdown(memoir.markdown_text ?? '')
      setEditStartYear(memoir.start_year?.toString() ?? '')
      setEditEndYear(memoir.end_year?.toString() ?? '')
      setEditing(true)
      setSearchParams({}, { replace: true })
    }
  }, [memoir, searchParams])

  // Edit state
  const [editTitle, setEditTitle] = useState('')
  const [editDateLabel, setEditDateLabel] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editMarkdown, setEditMarkdown] = useState('')
  const [editStartYear, setEditStartYear] = useState('')
  const [editEndYear, setEditEndYear] = useState('')

  const startEdit = () => {
    if (!memoir) return
    setEditTitle(memoir.title)
    setEditDateLabel(memoir.date_label ?? '')
    setEditDescription(memoir.description ?? '')
    setEditMarkdown(memoir.markdown_text ?? '')
    setEditStartYear(memoir.start_year?.toString() ?? '')
    setEditEndYear(memoir.end_year?.toString() ?? '')
    setEditing(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => updateMemoir(Number(id), {
      title: editTitle,
      date_label: editDateLabel || null,
      description: editDescription || null,
      markdown_text: editMarkdown,
      start_year: editStartYear ? parseInt(editStartYear) : null,
      end_year: editEndYear ? parseInt(editEndYear) : null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memoir', id] })
      setEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteMemoir(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memoirs'] })
      navigate(memoir?.parent ? `/memoir/${memoir.parent.id}` : '/memoirs')
    },
  })

  const voiceMutation = useMutation({
    mutationFn: (blob: Blob) => {
      if (!memoir?.entry_id) throw new Error('No backing entry')
      return uploadVoiceNote(memoir.entry_id, blob)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memoir', id] }),
  })

  const immichMutation = useMutation({
    mutationFn: (assetIds: string[]) => {
      if (!memoir?.entry_id) throw new Error('No backing entry')
      return attachImmichPhotos(memoir.entry_id, assetIds)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memoir', id] })
      setShowImmich(false)
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      if (!memoir?.entry_id) throw new Error('No backing entry')
      return uploadAttachment(memoir.entry_id, file)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memoir', id] }),
  })

  const deleteAttMutation = useMutation({
    mutationFn: (attachmentId: number) => {
      if (!memoir?.entry_id) throw new Error('No backing entry')
      return deleteAttachment(memoir.entry_id, attachmentId)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memoir', id] }),
  })

  const publishMutation = useMutation({
    mutationFn: (opts: { status?: string; visibility?: string }) => publishMemoir(Number(id), opts),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memoir', id] }),
  })

  const publishAllMutation = useMutation({
    mutationFn: (opts: { status?: string; visibility?: string }) => publishAll(Number(id), opts),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memoir', id] }),
  })

  const unpublishMutation = useMutation({
    mutationFn: () => unpublishMemoir(Number(id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memoir', id] }),
  })

  const excerptMutation = useMutation({
    mutationFn: () => generateExcerpt(Number(id)),
    onSuccess: (data) => {
      setLocalExcerpt(data.excerpt)
      queryClient.invalidateQueries({ queryKey: ['memoir', id] })
    },
  })

  const autoLinkMutation = useMutation({
    mutationFn: () => autoLinkEntries(Number(id)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['memoir', id] })
      alert(`Linked ${result.linked} entries`)
    },
  })

  // Add sub-page
  const [childTitle, setChildTitle] = useState('')
  const createChildMutation = useMutation({
    mutationFn: () => createMemoir({
      title: childTitle.trim(),
      parent_id: Number(id),
    }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['memoir', id] })
      setShowAddChild(false)
      setChildTitle('')
      navigate(`/memoir/${result.id}`)
    },
  })

  if (isLoading) return <div className="text-center py-12 text-text-secondary text-sm">Loading...</div>
  if (!memoir) return <div className="text-center py-12 text-text-secondary text-sm">Memoir not found</div>

  const images = memoir.attachments.filter(a => a.type === 'jpeg' || a.type === 'png')
  const audio = memoir.attachments.filter(a => a.type === 'audio')
  const videos = memoir.attachments.filter(a => ['mov', 'mp4', 'webm', 'ogg'].includes(a.type))
  const docs = memoir.attachments.filter(a => !['jpeg', 'png', 'audio', 'mov', 'mp4', 'webm', 'ogg'].includes(a.type))

  const copyLink = (att: typeof memoir.attachments[0]) => {
    const isImage = att.type === 'jpeg' || att.type === 'png'
    const name = att.filename || `attachment-${att.id}`
    const link = isImage
      ? `![${name}](/api/v1/media/${att.id})`
      : `[${name}](/api/v1/media/${att.id})`
    navigator.clipboard.writeText(link)
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm text-text-secondary mb-4">
        <Link to="/memoirs" className="hover:text-accent">Memoirs</Link>
        {memoir.parent && (
          <>
            <span>/</span>
            <Link to={`/memoir/${memoir.parent.id}`} className="hover:text-accent">{memoir.parent.title}</Link>
          </>
        )}
        <span>/</span>
        <span className="text-text-primary">{memoir.title}</span>
      </div>

      {/* Header */}
      {editing ? (
        <div className="bg-bg-card border border-border rounded-lg p-5 mb-6 space-y-3">
          <input value={editTitle} onChange={e => setEditTitle(e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded px-3 py-2 text-lg font-semibold text-text-primary" />
          <div className="grid grid-cols-3 gap-3">
            <input value={editStartYear} onChange={e => setEditStartYear(e.target.value)}
              placeholder="Start year" type="number"
              className="bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary" />
            <input value={editEndYear} onChange={e => setEditEndYear(e.target.value)}
              placeholder="End year" type="number"
              className="bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary" />
            <input value={editDateLabel} onChange={e => setEditDateLabel(e.target.value)}
              placeholder="Date label"
              className="bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary" />
          </div>
          <input value={editDescription} onChange={e => setEditDescription(e.target.value)}
            placeholder="Short description"
            className="w-full bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary" />
          <textarea value={editMarkdown} onChange={e => setEditMarkdown(e.target.value)}
            rows={12} placeholder="Write your memoir content here..."
            className="w-full bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary font-mono" />
          <div className="flex gap-2">
            <button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}
              className="px-4 py-2 bg-accent text-white rounded text-sm hover:bg-accent-hover disabled:opacity-50">
              {saveMutation.isPending ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setEditing(false)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="mb-6">
          <div className="flex items-start justify-between mb-2">
            <div>
              <h1 className="text-2xl font-bold text-text-primary">{memoir.title}</h1>
              <div className="flex items-center gap-3 mt-1 text-sm text-text-secondary">
                {memoir.date_label && (
                  <span className="bg-accent/10 text-accent px-2 py-0.5 rounded text-xs">{memoir.date_label}</span>
                )}
                {!memoir.date_label && memoir.start_year && (
                  <span className="bg-accent/10 text-accent px-2 py-0.5 rounded text-xs">
                    {memoir.start_year}{memoir.end_year && memoir.end_year !== memoir.start_year ? `–${memoir.end_year}` : ''}
                  </span>
                )}
                {memoir.description && <span>{memoir.description}</span>}
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={startEdit} className="px-3 py-1.5 text-xs bg-bg-card border border-border rounded hover:border-accent/30">Edit</button>
              <button onClick={() => { if (confirm('Delete this memoir?')) deleteMutation.mutate() }}
                className="px-3 py-1.5 text-xs text-danger border border-danger/30 rounded hover:bg-danger/10">Delete</button>
            </div>
          </div>

          {/* Markdown content */}
          {memoir.markdown_text && (
            <div className="bg-bg-card border border-border rounded-lg p-5 mb-4 max-w-none text-text-primary leading-relaxed space-y-2">
              <Markdown
                components={{
                  h1: ({ children }) => <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-xl font-semibold mt-3 mb-2">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-lg font-semibold mt-2 mb-1">{children}</h3>,
                  p: ({ children }) => <p className="mb-2">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
                  li: ({ children }) => <li>{children}</li>,
                  blockquote: ({ children }) => <blockquote className="border-l-4 border-accent/30 pl-4 italic text-text-secondary my-2">{children}</blockquote>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  em: ({ children }) => <em className="italic">{children}</em>,
                  hr: () => <hr className="border-border my-4" />,
                  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-hover underline">{children}</a>,
                }}
              >
                {memoir.markdown_text}
              </Markdown>
            </div>
          )}
        </div>
      )}

      {/* Publish to Ghost */}
      <div className="bg-bg-card border border-border rounded-lg p-4 mb-6">
        <h3 className="text-sm font-medium text-text-secondary mb-3">Publish to Blog</h3>
        <div className="flex items-center gap-3 mb-3">
          <select
            value={memoir.ghost_visibility || 'members'}
            onChange={e => updateMemoir(Number(id), { ghost_visibility: e.target.value }).then(() => queryClient.invalidateQueries({ queryKey: ['memoir', id] }))}
            className="bg-bg-secondary border border-border rounded px-2 py-1 text-xs text-text-primary"
          >
            <option value="public">Public</option>
            <option value="members">Members Only</option>
            <option value="paid">Paid Subscribers</option>
          </select>
          {memoir.ghost_status === 'published' ? (
            <>
              <span className="text-xs text-success">Published</span>
              <button onClick={() => publishMutation.mutate({ visibility: memoir.ghost_visibility || undefined })}
                disabled={publishMutation.isPending}
                className="px-3 py-1 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50">
                {publishMutation.isPending ? '...' : 'Update'}
              </button>
              <button onClick={() => unpublishMutation.mutate()}
                disabled={unpublishMutation.isPending}
                className="px-3 py-1 text-xs text-warning border border-warning/30 rounded hover:bg-warning/10">
                Unpublish
              </button>
            </>
          ) : (
            <>
              {memoir.ghost_status === 'draft' && <span className="text-xs text-text-secondary">Draft on Ghost</span>}
              <button onClick={() => publishMutation.mutate({ visibility: memoir.ghost_visibility || undefined })}
                disabled={publishMutation.isPending}
                className="px-3 py-1 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50">
                {publishMutation.isPending ? '...' : 'Publish'}
              </button>
              {!memoir.parent_id && memoir.child_count > 0 && (
                <button onClick={() => publishAllMutation.mutate({ visibility: memoir.ghost_visibility || undefined })}
                  disabled={publishAllMutation.isPending}
                  className="px-3 py-1 text-xs bg-bg-hover border border-border rounded hover:border-accent/30">
                  {publishAllMutation.isPending ? '...' : `Publish All (${memoir.child_count + 1})`}
                </button>
              )}
            </>
          )}
        </div>
        <div className="space-y-2 text-xs mb-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-text-secondary block mb-0.5">Tags</label>
              <input
                value={localTags ?? memoir.tags?.join(', ') ?? ''}
                onChange={e => setLocalTags(e.target.value)}
                onBlur={e => { updateMemoir(Number(id), { tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) }).then(() => { queryClient.invalidateQueries({ queryKey: ['memoir', id] }); setLocalTags(null) }) }}
                placeholder="memoir, personal, history"
                className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-text-primary"
              />
            </div>
            <div>
              <label className="text-text-secondary block mb-0.5">URL slug</label>
              <input
                value={localSlug ?? memoir.slug ?? ''}
                onChange={e => setLocalSlug(e.target.value)}
                onBlur={e => { updateMemoir(Number(id), { slug: e.target.value }).then(() => { queryClient.invalidateQueries({ queryKey: ['memoir', id] }); setLocalSlug(null) }) }}
                placeholder="the-playhouse-years"
                className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-text-primary"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-text-secondary block mb-0.5">Published date</label>
              <input
                type="date"
                value={memoir.published_date || ''}
                onChange={e => updateMemoir(Number(id), { published_date: e.target.value || null }).then(() => queryClient.invalidateQueries({ queryKey: ['memoir', id] }))}
                className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-text-primary"
              />
            </div>
            {images.length > 0 && (
              <div>
                <label className="text-text-secondary block mb-0.5">Featured image</label>
                <select
                  value={memoir.feature_image_attachment_id ?? ''}
                  onChange={e => updateMemoir(Number(id), { feature_image_attachment_id: e.target.value ? Number(e.target.value) : null }).then(() => queryClient.invalidateQueries({ queryKey: ['memoir', id] }))}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-text-primary"
                >
                  <option value="">None</option>
                  {images.map(att => (
                    <option key={att.id} value={att.id}>{att.filename || `Photo ${att.id}`}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <label className="text-text-secondary">Excerpt</label>
              <button
                onClick={() => excerptMutation.mutate()}
                disabled={excerptMutation.isPending}
                className="px-2 py-0.5 text-accent border border-accent/30 rounded hover:bg-accent/10 disabled:opacity-50"
              >
                {excerptMutation.isPending ? 'Generating...' : 'Generate'}
              </button>
            </div>
            <textarea
              value={localExcerpt ?? memoir.meta_description ?? ''}
              onChange={e => setLocalExcerpt(e.target.value)}
              onBlur={e => { updateMemoir(Number(id), { meta_description: e.target.value || null }).then(() => { queryClient.invalidateQueries({ queryKey: ['memoir', id] }); setLocalExcerpt(null) }) }}
              rows={2}
              placeholder="A compelling excerpt for the blog post..."
              className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-text-primary"
            />
          </div>
          <div>
            <label className="text-text-secondary block mb-0.5">Publish on</label>
            <input
              type="datetime-local"
              value={publishOn}
              onChange={e => setPublishOn(e.target.value)}
              className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-text-primary"
            />
          </div>
        </div>
        {memoir.ghost_post_id && (
          <a href={`https://blog.mees.st/${memoir.slug || ''}`} target="_blank" rel="noopener noreferrer"
            className="text-xs text-accent hover:text-accent-hover mt-2 inline-block">
            View on blog
          </a>
        )}
      </div>

      {/* Attachments — unified section for all media types */}
      {memoir.attachments.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-secondary mb-3">Attachments ({memoir.attachments.length})</h3>

          {/* Images grid */}
          {images.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-3">
              {images.map(att => (
                <div key={att.id} className="relative group">
                  <img src={att.thumbnail_url} alt={att.caption || ''} loading="lazy"
                    className="w-full aspect-square object-cover rounded-lg" />
                  <div className="absolute bottom-1 left-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => copyLink(att)}
                      className="px-1.5 py-0.5 bg-black/60 text-white rounded text-xs">Link</button>
                    {editing && (
                      <button onClick={() => deleteAttMutation.mutate(att.id)}
                        className="px-1.5 py-0.5 bg-red-600/80 text-white rounded text-xs ml-auto">x</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Documents and other files */}
          {docs.length > 0 && (
            <div className="space-y-1 mb-3">
              {docs.map(att => (
                <div key={att.id} className="flex items-center gap-2 bg-bg-card border border-border rounded-lg px-3 py-2">
                  <span className="text-xs font-mono bg-bg-hover px-1.5 py-0.5 rounded uppercase">{att.type}</span>
                  <a href={att.media_url} target="_blank" rel="noopener noreferrer"
                    className="text-sm text-accent hover:text-accent-hover truncate flex-1">{att.filename || `file-${att.id}`}</a>
                  <button onClick={() => copyLink(att)}
                    className="text-xs text-text-secondary hover:text-accent px-2 py-0.5 border border-border rounded">Link</button>
                  {editing && (
                    <button onClick={() => deleteAttMutation.mutate(att.id)}
                      className="text-xs text-danger px-2 py-0.5">x</button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Videos */}
          {videos.length > 0 && (
            <div className="space-y-2 mb-3">
              {videos.map(att => (
                <div key={att.id} className="bg-bg-card border border-border rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-mono bg-bg-hover px-1.5 py-0.5 rounded uppercase">{att.type}</span>
                    <span className="text-sm text-text-primary truncate flex-1">{att.filename || `video-${att.id}`}</span>
                    <button onClick={() => copyLink(att)}
                      className="text-xs text-text-secondary hover:text-accent px-2 py-0.5 border border-border rounded">Link</button>
                    {editing && (
                      <button onClick={() => deleteAttMutation.mutate(att.id)}
                        className="text-xs text-danger px-2 py-0.5">x</button>
                    )}
                  </div>
                  <video controls src={att.media_url} className="w-full rounded" />
                </div>
              ))}
            </div>
          )}

          {/* Audio / voice notes */}
          {audio.length > 0 && (
            <div className="space-y-2 mb-3">
              {audio.map(att => (
                <div key={att.id} className="bg-bg-card border border-border rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-text-secondary">Voice note</span>
                    <button onClick={() => copyLink(att)}
                      className="text-xs text-text-secondary hover:text-accent px-2 py-0.5 border border-border rounded">Link</button>
                  </div>
                  <audio controls src={att.media_url} className="w-full mb-1" />
                  {att.transcription && (
                    <p className="text-xs text-text-secondary italic">{att.transcription}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add content actions */}
      <div className="flex flex-wrap gap-2 mb-6">
        <VoiceRecorder
          hasRecording={hasRecording}
          onRecorded={(blob) => { setHasRecording(true); voiceMutation.mutate(blob) }}
          onClear={() => setHasRecording(false)}
        />
        <button onClick={() => setShowImmich(!showImmich)}
          className="px-3 py-1.5 text-xs bg-bg-card border border-border rounded hover:border-accent/30">
          {showImmich ? 'Cancel' : 'Add from Immich'}
        </button>
        <label className="px-3 py-1.5 text-xs bg-bg-card border border-border rounded hover:border-accent/30 cursor-pointer">
          Upload File
          <input type="file" className="hidden"
            onChange={e => { if (e.target.files?.[0]) uploadMutation.mutate(e.target.files[0]) }} />
        </label>
        {memoir.start_year && (
          <button onClick={() => autoLinkMutation.mutate()} disabled={autoLinkMutation.isPending}
            className="px-3 py-1.5 text-xs bg-bg-card border border-border rounded hover:border-accent/30">
            {autoLinkMutation.isPending ? 'Linking...' : 'Auto-link Entries'}
          </button>
        )}
      </div>

      {/* Immich browser */}
      {showImmich && (
        <div className="mb-6">
          <ImmichBrowser selectedIds={immichIds} onSelectionChange={setImmichIds} />
          {immichIds.length > 0 && (
            <button onClick={() => immichMutation.mutate(immichIds)}
              disabled={immichMutation.isPending}
              className="mt-2 px-4 py-2 bg-accent text-white rounded text-sm hover:bg-accent-hover disabled:opacity-50">
              {immichMutation.isPending ? 'Attaching...' : `Attach ${immichIds.length} photo${immichIds.length !== 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      )}

      {/* Sub-pages */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-text-secondary">
            Sub-pages ({memoir.children.length})
          </h3>
          <button onClick={() => setShowAddChild(!showAddChild)}
            className="px-3 py-1.5 text-xs bg-bg-card border border-border rounded hover:border-accent/30">
            {showAddChild ? 'Cancel' : 'Add Sub-page'}
          </button>
        </div>

        {showAddChild && (
          <div className="flex gap-2 mb-3">
            <input value={childTitle} onChange={e => setChildTitle(e.target.value)}
              placeholder="Sub-page title"
              className="flex-1 bg-bg-secondary border border-border rounded px-3 py-2 text-sm text-text-primary" />
            <button onClick={() => createChildMutation.mutate()}
              disabled={!childTitle.trim() || createChildMutation.isPending}
              className="px-4 py-2 bg-accent text-white rounded text-sm hover:bg-accent-hover disabled:opacity-50">
              Create
            </button>
          </div>
        )}

        <div className="space-y-2">
          {memoir.children.map(child => (
            <div key={child.id} onClick={() => navigate(`/memoir/${child.id}`)}
              className="bg-bg-card border border-border rounded-lg p-4 hover:border-accent/30 transition-colors cursor-pointer">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-text-primary">{child.title}</span>
                  {child.date_label && (
                    <span className="ml-2 text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">{child.date_label}</span>
                  )}
                </div>
                {child.attachment_count > 0 && (
                  <span className="text-xs text-text-secondary">{child.attachment_count} photos</span>
                )}
              </div>
              {child.description && (
                <p className="text-xs text-text-secondary mt-1">{child.description}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Linked journal entries */}
      {memoir.linked_entries.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-secondary mb-3">
            Linked Entries ({memoir.linked_entries.length})
          </h3>
          <div className="space-y-1">
            {memoir.linked_entries.map(entry => (
              <Link key={entry.id} to={`/entry/${entry.id}`}
                className="block bg-bg-card border border-border rounded p-3 hover:border-accent/30 transition-colors">
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-text-secondary">
                    {new Date(entry.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </span>
                  {entry.place_name && <span className="text-text-secondary">{entry.place_name}</span>}
                </div>
                {entry.preview && (
                  <p className="text-xs text-text-secondary mt-1 truncate">{entry.preview}</p>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
