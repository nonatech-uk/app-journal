import { useParams } from 'react-router-dom'
import { useEntry, useEnrichment } from '../hooks/useEntry'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toggleStar } from '../api/entries'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function EntryDetail() {
  const { id } = useParams()
  const entryId = id ? Number(id) : undefined
  const { data: entry, isLoading } = useEntry(entryId)
  const { data: enrichment } = useEnrichment(entryId)
  const queryClient = useQueryClient()

  const starMutation = useMutation({
    mutationFn: () => toggleStar(entryId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry', entryId] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })

  if (isLoading) return <div className="text-text-secondary">Loading...</div>
  if (!entry) return <div className="text-text-secondary">Entry not found</div>

  // Simple markdown-to-html: convert image refs and basic formatting
  const renderText = (text: string) => {
    // Strip DayOne moment refs for now
    const cleaned = text.replace(/!\[.*?\]\(dayone-moment:\/\/[^)]+\)/g, '').trim()
    return cleaned.split('\n').map((line, i) => (
      <p key={i} className={`${line.trim() === '' ? 'h-3' : ''}`}>{line}</p>
    ))
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center gap-3 mb-1">
          <span className="text-sm text-text-secondary">{formatDate(entry.created_at)}</span>
          {entry.journal_name && (
            <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent">{entry.journal_name}</span>
          )}
          <button
            onClick={() => starMutation.mutate()}
            className={`text-lg ${entry.starred ? 'text-warning' : 'text-text-secondary hover:text-warning'} transition-colors`}
          >
            {entry.starred ? '★' : '☆'}
          </button>
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
          {entry.attachments.length > 0 && (
            <div className="mb-4">
              <div className={`grid gap-2 ${entry.attachments.length === 1 ? '' : 'grid-cols-2 lg:grid-cols-3'}`}>
                {entry.attachments.map((att) => (
                  <div key={att.id} className="rounded-lg overflow-hidden bg-bg-hover">
                    {att.type === 'mov' || att.type === 'mp4' ? (
                      <video
                        src={att.media_url!}
                        controls
                        className="w-full"
                        preload="metadata"
                      />
                    ) : att.type === 'pdf' ? (
                      <a href={att.media_url!} target="_blank" rel="noreferrer"
                         className="flex items-center justify-center h-24 text-accent text-sm">
                        PDF: {att.filename || 'document.pdf'}
                      </a>
                    ) : (
                      <img
                        src={att.media_url!}
                        alt={att.caption || ''}
                        className="w-full cursor-pointer"
                        loading="lazy"
                      />
                    )}
                    {att.caption && (
                      <p className="text-xs text-text-secondary p-1">{att.caption}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Text */}
          {entry.markdown_text && (
            <div className="prose prose-sm max-w-none text-text-primary leading-relaxed">
              {renderText(entry.markdown_text)}
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
          {/* Location */}
          {entry.location && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">Location</h4>
              <div className="text-sm">{entry.location.place_name}</div>
              {entry.location.locality && (
                <div className="text-xs text-text-secondary">
                  {entry.location.locality}
                  {entry.location.admin_area ? `, ${entry.location.admin_area}` : ''}
                  {entry.location.country ? `, ${entry.location.country}` : ''}
                </div>
              )}
            </div>
          )}

          {/* Weather */}
          {entry.weather && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">Weather</h4>
              <div className="text-sm">
                {entry.weather.temp_celsius !== null && `${Math.round(entry.weather.temp_celsius)}°C`}
                {entry.weather.conditions && ` — ${entry.weather.conditions}`}
              </div>
              {entry.weather.relative_humidity !== null && (
                <div className="text-xs text-text-secondary">
                  Humidity: {entry.weather.relative_humidity}%
                  {entry.weather.wind_speed_kph !== null && ` | Wind: ${Math.round(entry.weather.wind_speed_kph!)} kph`}
                </div>
              )}
            </div>
          )}

          {/* Music */}
          {entry.music && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">Playing</h4>
              <div className="text-sm">{entry.music.track}</div>
              <div className="text-xs text-text-secondary">{entry.music.artist} — {entry.music.album}</div>
            </div>
          )}

          {/* Enrichment — Scrobbles */}
          {enrichment?.scrobbles && enrichment.scrobbles.length > 0 && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">
                Scrobbles ({enrichment.scrobbles.length})
              </h4>
              <div className="space-y-1 max-h-40 overflow-auto">
                {enrichment.scrobbles.map((s, i) => (
                  <div key={i} className="text-xs">
                    <span className="text-text-primary">{s.track}</span>
                    <span className="text-text-secondary"> — {s.artist}</span>
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

          {/* Enrichment — GPS */}
          {enrichment?.gps_summary && (
            <div className="bg-bg-card border border-border rounded-lg p-3">
              <h4 className="text-xs font-medium text-text-secondary mb-1">GPS Location</h4>
              <div className="text-sm">
                {enrichment.gps_summary.city}, {enrichment.gps_summary.country}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
