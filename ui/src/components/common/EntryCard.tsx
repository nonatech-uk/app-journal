import { Link } from 'react-router-dom'
import type { EntrySummary } from '../../api/types'

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function EntryCard({ entry }: { entry: EntrySummary }) {
  return (
    <Link
      to={`/entry/${entry.id}`}
      className="block bg-bg-card rounded-lg border border-border hover:border-accent/30 transition-colors overflow-hidden"
    >
      <div className="flex">
        {entry.thumbnail_url && (
          <div className="shrink-0">
            <img
              src={entry.thumbnail_url}
              alt=""
              className="h-24 w-auto rounded-l-lg"
              loading="lazy"
            />
          </div>
        )}
        <div className="flex-1 p-3 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-text-secondary">{formatDate(entry.created_at)}</span>
            {entry.starred && <span className="text-xs text-warning">★</span>}
            {entry.journal_name && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">
                {entry.journal_name}
              </span>
            )}
          </div>
          {entry.text_preview && (
            <p className="text-sm text-text-primary line-clamp-2 mb-1">
              {entry.text_preview
                .replace(/!\[.*$/g, '')
                .replace(/\\([!\-().#>])/g, '$1')
                .replace(/^#{1,6}\s+/gm, '')
                .replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1')
                .replace(/_{1,3}([^_]+)_{1,3}/g, '$1')
                .replace(/~~([^~]+)~~/g, '$1')
                .replace(/`([^`]+)`/g, '$1')
                .replace(/^\s*[-*+]\s+/gm, '')
                .replace(/^\s*>\s+/gm, '')
                .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
                .trim()}
            </p>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            {entry.location?.place_name && (
              <span className="text-xs text-text-secondary">
                {entry.location.place_label
                  ? `${entry.location.place_label} (${entry.location.place_name})`
                  : entry.location.place_name}
                {entry.location.locality ? `, ${entry.location.locality}` : ''}
              </span>
            )}
            {entry.weather && entry.weather.temp_celsius !== null && (
              <span className="text-xs text-text-secondary">
                {Math.round(entry.weather.temp_celsius)}°C {entry.weather.conditions || ''}
              </span>
            )}
            {entry.music?.track && (
              <span className="text-xs text-text-secondary">
                ♫ {entry.music.artist} — {entry.music.track}
              </span>
            )}
            {entry.attachment_count > 0 && (
              <span className="text-xs text-text-secondary">
                {entry.attachment_count} {entry.attachment_count === 1 ? 'attachment' : 'attachments'}
              </span>
            )}
          </div>
          {entry.tags.length > 0 && (
            <div className="flex gap-1 mt-1 flex-wrap">
              {entry.tags.map((t) => (
                <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-hover text-text-secondary">
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </Link>
  )
}
