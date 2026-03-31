import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchContext, createEntry, uploadVoiceNote } from '../api/entries'
import { fetchJournals } from '../api/meta'
import type { EntryCreatePayload, ContextScrobble } from '../api/types'
import VoiceRecorder from '../components/VoiceRecorder'
import ImmichBrowser from '../components/ImmichBrowser'

export default function NewEntry() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Form state
  const [text, setText] = useState('')
  const [tags, setTags] = useState('')
  const [starred, setStarred] = useState(false)
  const [journalId, setJournalId] = useState<number | null>(null)
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(null)
  const [immichIds, setImmichIds] = useState<string[]>([])
  const [showImmich, setShowImmich] = useState(false)

  // Context state (dismissible)
  const [includeLocation, setIncludeLocation] = useState(true)
  const [includeWeather, setIncludeWeather] = useState(true)
  const [selectedScrobble, setSelectedScrobble] = useState<ContextScrobble | null>(null)
  const [scrobbleAutoSet, setScrobbleAutoSet] = useState(false)

  // Fetch context on mount
  const { data: ctx, isLoading: ctxLoading } = useQuery({
    queryKey: ['context', 'now'],
    queryFn: fetchContext,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })

  // Auto-select first scrobble once
  if (ctx?.scrobbles?.length && !scrobbleAutoSet) {
    setSelectedScrobble(ctx.scrobbles[0])
    setScrobbleAutoSet(true)
  }

  // Fetch journals for dropdown
  const { data: journals } = useQuery({
    queryKey: ['journals'],
    queryFn: fetchJournals,
    staleTime: 5 * 60_000,
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const loc = includeLocation && ctx?.location ? ctx.location : null
      const weather = includeWeather && ctx?.weather ? ctx.weather : null

      const payload: EntryCreatePayload = {
        markdown_text: text,
        journal_id: journalId,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        starred,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        location: loc ? {
          latitude: loc.latitude,
          longitude: loc.longitude,
          place_name: loc.place_name,
          locality: loc.locality,
          admin_area: loc.admin_area,
          country: loc.country,
        } : null,
        weather: weather ? {
          temp_celsius: weather.temp_celsius,
          conditions: weather.conditions,
          weather_code: weather.weather_code,
          relative_humidity: weather.relative_humidity,
          wind_speed_kph: weather.wind_speed_kph,
          wind_bearing: weather.wind_bearing,
          pressure_mb: weather.pressure_mb,
        } : null,
        music: selectedScrobble ? {
          track: selectedScrobble.track,
          artist: selectedScrobble.artist,
          album: selectedScrobble.album,
        } : null,
        immich_asset_ids: immichIds,
      }

      const entry = await createEntry(payload)

      // Upload voice note if recorded
      if (voiceBlob) {
        return uploadVoiceNote(entry.id, voiceBlob)
      }
      return entry
    },
    onSuccess: (entry) => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      navigate(`/entry/${entry.id}`)
    },
  })

  const handleSave = useCallback(() => {
    if (!text.trim() && !voiceBlob && immichIds.length === 0) return
    saveMutation.mutate()
  }, [text, voiceBlob, immichIds, saveMutation])

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">New Entry</h2>
        <div className="flex gap-2">
          <button
            onClick={() => navigate(-1)}
            className="text-sm px-3 py-1.5 rounded border border-border text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending || (!text.trim() && !voiceBlob && immichIds.length === 0)}
            className="text-sm px-4 py-1.5 rounded bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Main editor */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Journal + Star */}
          <div className="flex items-center gap-3">
            <select
              value={journalId ?? ''}
              onChange={(e) => setJournalId(e.target.value ? Number(e.target.value) : null)}
              className="bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
            >
              <option value="">No journal</option>
              {journals?.map((j) => (
                <option key={j.id} value={j.id}>{j.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setStarred(!starred)}
              className={`text-lg transition-colors ${starred ? 'text-warning' : 'text-text-secondary hover:text-warning'}`}
            >
              {starred ? '★' : '☆'}
            </button>
          </div>

          {/* Text editor */}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What's on your mind?"
            className="w-full h-64 bg-bg-secondary border border-border rounded-lg p-3 text-text-primary text-sm leading-relaxed resize-y focus:outline-none focus:border-accent/50"
            autoFocus
          />

          {/* Voice recorder */}
          <VoiceRecorder
            onRecorded={setVoiceBlob}
            onClear={() => setVoiceBlob(null)}
            hasRecording={!!voiceBlob}
          />

          {/* Tags */}
          <div>
            <label className="text-xs text-text-secondary block mb-1">Tags (comma-separated)</label>
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className="w-full bg-bg-secondary border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
              placeholder="travel, food, thoughts..."
            />
          </div>

          {/* Immich photos */}
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

          {saveMutation.isError && (
            <div className="text-sm text-red-500">
              Failed to save entry. Please try again.
            </div>
          )}
        </div>

        {/* Context sidebar */}
        <div className="w-64 shrink-0 space-y-4">
          {ctxLoading && (
            <div className="text-xs text-text-secondary">Loading context...</div>
          )}

          {/* Location */}
          {ctx?.location && includeLocation && (
            <div className="bg-bg-card border border-border rounded-lg p-3 relative">
              <button
                type="button"
                onClick={() => setIncludeLocation(false)}
                className="absolute top-2 right-2 text-text-secondary hover:text-text-primary text-xs"
              >
                ×
              </button>
              <h4 className="text-xs font-medium text-text-secondary mb-1">Location</h4>
              {ctx.location.place_name && (
                <div className="text-sm">{ctx.location.place_name}</div>
              )}
              {ctx.location.locality && (
                <div className="text-xs text-text-secondary">
                  {ctx.location.locality}
                  {ctx.location.admin_area ? `, ${ctx.location.admin_area}` : ''}
                  {ctx.location.country ? `, ${ctx.location.country}` : ''}
                </div>
              )}
              {!ctx.location.place_name && !ctx.location.locality && (
                <div className="text-xs text-text-secondary">
                  {ctx.location.latitude.toFixed(4)}, {ctx.location.longitude.toFixed(4)}
                </div>
              )}
            </div>
          )}

          {/* Weather */}
          {ctx?.weather && includeWeather && (
            <div className="bg-bg-card border border-border rounded-lg p-3 relative">
              <button
                type="button"
                onClick={() => setIncludeWeather(false)}
                className="absolute top-2 right-2 text-text-secondary hover:text-text-primary text-xs"
              >
                ×
              </button>
              <h4 className="text-xs font-medium text-text-secondary mb-1">Weather</h4>
              <div className="text-sm">
                {ctx.weather.temp_celsius !== null && `${Math.round(ctx.weather.temp_celsius)}°C`}
                {ctx.weather.conditions && ` — ${ctx.weather.conditions}`}
              </div>
              {ctx.weather.relative_humidity !== null && (
                <div className="text-xs text-text-secondary">
                  Humidity: {ctx.weather.relative_humidity}%
                  {ctx.weather.wind_speed_kph !== null && ` | Wind: ${Math.round(ctx.weather.wind_speed_kph!)} kph`}
                </div>
              )}
            </div>
          )}

          {/* Now Playing / Recent Scrobbles */}
          {ctx?.scrobbles && ctx.scrobbles.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3 relative">
              {selectedScrobble && (
                <button
                  type="button"
                  onClick={() => setSelectedScrobble(null)}
                  className="absolute top-2 right-2 text-text-secondary hover:text-text-primary text-xs"
                >
                  ×
                </button>
              )}
              <h4 className="text-xs font-medium text-text-secondary mb-1">Now Playing</h4>
              <div className="space-y-1.5">
                {ctx.scrobbles.slice(0, 5).map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setSelectedScrobble(
                      selectedScrobble?.track === s.track && selectedScrobble?.artist === s.artist
                        ? null : s
                    )}
                    className={`block w-full text-left rounded px-1.5 py-1 transition-colors ${
                      selectedScrobble?.track === s.track && selectedScrobble?.artist === s.artist
                        ? 'bg-accent/10 border border-accent/30'
                        : 'hover:bg-bg-hover border border-transparent'
                    }`}
                  >
                    <div className="text-xs text-text-primary">{s.track}</div>
                    <div className="text-xs text-text-secondary">{s.artist}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Recently Watched */}
          {ctx?.tautulli_watches && ctx.tautulli_watches.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">Recently Watched</h4>
              <div className="space-y-1">
                {ctx.tautulli_watches.map((w, i) => (
                  <div key={i} className="text-xs">
                    <span className="text-text-primary">{w.title}</span>
                    {w.media_type && (
                      <span className="text-text-secondary ml-1">({w.media_type})</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Dismissed context restore */}
          {ctx && (!includeLocation || !includeWeather || !selectedScrobble) && (
            <div className="flex flex-wrap gap-1">
              {!includeLocation && ctx.location && (
                <button
                  type="button"
                  onClick={() => setIncludeLocation(true)}
                  className="text-xs px-2 py-0.5 rounded border border-border text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
                >
                  + Location
                </button>
              )}
              {!includeWeather && ctx.weather && (
                <button
                  type="button"
                  onClick={() => setIncludeWeather(true)}
                  className="text-xs px-2 py-0.5 rounded border border-border text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
                >
                  + Weather
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
