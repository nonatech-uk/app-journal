import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { searchEntries } from '../api/meta'
import EntryCard from '../components/common/EntryCard'

export default function Search() {
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['search', submitted],
    queryFn: () => searchEntries(submitted, 50),
    enabled: !!submitted,
  })

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Search</h2>
      <form
        onSubmit={(e) => { e.preventDefault(); setSubmitted(query) }}
        className="flex gap-2 mb-4"
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search entries..."
          className="flex-1 px-3 py-2 bg-bg-secondary border border-border rounded-md text-sm focus:outline-none focus:border-accent"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-accent text-white text-sm rounded-md hover:bg-accent-hover transition-colors"
        >
          Search
        </button>
      </form>

      {isLoading && <div className="text-text-secondary text-sm">Searching...</div>}

      {data && (
        <>
          <div className="text-sm text-text-secondary mb-2">
            {data.total} {data.total === 1 ? 'result' : 'results'}
          </div>
          <div className="space-y-2">
            {data.items.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
