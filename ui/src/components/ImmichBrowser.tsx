import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { searchImmich, searchImmichRecent } from '../api/entries'
import type { ImmichAsset } from '../api/types'

interface Props {
  selectedIds: string[]
  onSelectionChange: (ids: string[]) => void
}

export default function ImmichBrowser({ selectedIds, onSelectionChange }: Props) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [tab, setTab] = useState<'recent' | 'search'>('recent')
  const [debounceTimer, setDebounceTimer] = useState<number | null>(null)

  const handleQueryChange = useCallback(
    (value: string) => {
      setQuery(value)
      if (debounceTimer) clearTimeout(debounceTimer)
      const timer = window.setTimeout(() => {
        setDebouncedQuery(value)
        if (value) setTab('search')
      }, 500)
      setDebounceTimer(timer)
    },
    [debounceTimer],
  )

  const recentQuery = useQuery({
    queryKey: ['immich', 'recent'],
    queryFn: () => searchImmichRecent(7, 24),
    enabled: tab === 'recent',
    staleTime: 60_000,
  })

  const searchQuery = useQuery({
    queryKey: ['immich', 'search', debouncedQuery],
    queryFn: () => searchImmich(debouncedQuery, 24),
    enabled: tab === 'search' && debouncedQuery.length > 0,
    staleTime: 30_000,
  })

  const assets = tab === 'search' ? searchQuery.data : recentQuery.data
  const isLoading = tab === 'search' ? searchQuery.isLoading : recentQuery.isLoading

  const toggleAsset = useCallback(
    (id: string) => {
      if (selectedIds.includes(id)) {
        onSelectionChange(selectedIds.filter((s) => s !== id))
      } else {
        onSelectionChange([...selectedIds, id])
      }
    },
    [selectedIds, onSelectionChange],
  )

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="p-2 border-b border-border bg-bg-secondary">
        <input
          type="text"
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Search photos..."
          className="w-full bg-bg-primary border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent/50"
        />
        <div className="flex gap-2 mt-1.5">
          <button
            type="button"
            onClick={() => setTab('recent')}
            className={`text-xs px-2 py-0.5 rounded ${tab === 'recent' ? 'bg-accent/15 text-accent' : 'text-text-secondary hover:text-text-primary'}`}
          >
            Recent
          </button>
          <button
            type="button"
            onClick={() => { setTab('search'); if (!debouncedQuery) setDebouncedQuery(query) }}
            className={`text-xs px-2 py-0.5 rounded ${tab === 'search' ? 'bg-accent/15 text-accent' : 'text-text-secondary hover:text-text-primary'}`}
          >
            Search
          </button>
          {selectedIds.length > 0 && (
            <span className="text-xs text-accent ml-auto">{selectedIds.length} selected</span>
          )}
        </div>
      </div>

      <div className="p-2 max-h-64 overflow-auto">
        {isLoading ? (
          <div className="text-xs text-text-secondary text-center py-4">Loading...</div>
        ) : assets && assets.length > 0 ? (
          <div className="grid grid-cols-4 gap-1.5">
            {assets.map((asset: ImmichAsset) => (
              <button
                key={asset.id}
                type="button"
                onClick={() => toggleAsset(asset.id)}
                className={`aspect-square rounded overflow-hidden border-2 transition-colors ${
                  selectedIds.includes(asset.id)
                    ? 'border-accent ring-1 ring-accent/30'
                    : 'border-transparent hover:border-border'
                }`}
              >
                <img
                  src={asset.thumbnail_url}
                  alt={asset.original_filename || ''}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-secondary text-center py-4">
            {tab === 'search' && !debouncedQuery ? 'Type to search photos' : 'No photos found'}
          </div>
        )}
      </div>
    </div>
  )
}
