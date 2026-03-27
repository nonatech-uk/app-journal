import { useQuery } from '@tanstack/react-query'
import { fetchMapEntries } from '../api/meta'

export default function MapView() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ['map-entries'],
    queryFn: () => fetchMapEntries(),
  })

  if (isLoading) return <div className="text-text-secondary">Loading...</div>

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Map</h2>
      <div className="bg-bg-card border border-border rounded-lg p-4">
        <p className="text-sm text-text-secondary mb-4">
          {entries?.length.toLocaleString()} entries with locations.
          Map rendering will use Leaflet — for now, here are the top locations:
        </p>
        <div className="space-y-1 max-h-96 overflow-auto">
          {entries?.slice(0, 100).map((e) => (
            <a
              key={e.id}
              href={`/entry/${e.id}`}
              className="flex items-center gap-2 text-sm hover:bg-bg-hover px-2 py-1 rounded"
            >
              <span className="text-text-secondary text-xs w-24 shrink-0">
                {new Date(e.created_at).toLocaleDateString('en-GB')}
              </span>
              <span className="truncate">{e.place_name || `${e.latitude.toFixed(2)}, ${e.longitude.toFixed(2)}`}</span>
              {e.text_preview && (
                <span className="text-text-secondary text-xs truncate ml-auto">{e.text_preview}</span>
              )}
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
