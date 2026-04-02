import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEntries } from '../hooks/useEntries'
import EntryCard from '../components/common/EntryCard'
import { useQuery } from '@tanstack/react-query'
import { fetchJournals, fetchOnThisDay } from '../api/meta'
import type { OnThisDayEntry } from '../api/types'

export default function Timeline() {
  const [searchParams, setSearchParams] = useSearchParams()
  const yearParam = searchParams.get('year') ? Number(searchParams.get('year')) : null
  const monthParam = searchParams.get('month') ? Number(searchParams.get('month')) : null

  const [journalId, setJournalId] = useState<number | null>(null)
  const [_tag] = useState<string | null>(null)
  const [starred, setStarred] = useState<boolean | null>(null)

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useEntries({ journal_id: journalId, tag: _tag, starred, year: yearParam, month: monthParam })

  const { data: journals } = useQuery({ queryKey: ['journals'], queryFn: fetchJournals })
  const { data: onThisDay } = useQuery({ queryKey: ['on-this-day'], queryFn: () => fetchOnThisDay() })

  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sentinelRef.current || !hasNextPage) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage() },
      { rootMargin: '200px' },
    )
    obs.observe(sentinelRef.current)
    return () => obs.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const entries = data?.pages.flatMap((p) => p.items) ?? []
  const total = data?.pages[0]?.total

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold">
            Timeline
            {yearParam && (
              <span className="text-base font-normal text-text-secondary ml-2">
                {monthParam ? new Date(yearParam, monthParam - 1).toLocaleDateString('en-GB', { month: 'long' }) + ' ' : ''}{yearParam}
                <button
                  onClick={() => setSearchParams({})}
                  className="ml-2 text-xs text-accent hover:underline"
                >
                  clear
                </button>
              </span>
            )}
          </h2>
          {total !== null && total !== undefined && (
            <span className="text-sm text-text-secondary">{total.toLocaleString()} entries</span>
          )}
        </div>
        <div className="flex gap-2">
          <select
            className="text-sm bg-bg-secondary border border-border rounded px-2 py-1"
            value={journalId ?? ''}
            onChange={(e) => setJournalId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All Journals</option>
            {journals?.map((j) => (
              <option key={j.id} value={j.id}>{j.name} ({j.entry_count})</option>
            ))}
          </select>
          <button
            onClick={() => setStarred(starred === true ? null : true)}
            className={`text-sm px-2 py-1 rounded border transition-colors ${
              starred ? 'bg-warning/15 border-warning text-warning' : 'bg-bg-secondary border-border text-text-secondary'
            }`}
          >
            ★ Starred
          </button>
        </div>
      </div>

      {/* On This Day */}
      {onThisDay && onThisDay.length > 0 && (
        <div className="mb-6 p-4 bg-accent/5 rounded-lg border border-accent/20">
          <h3 className="text-sm font-medium text-accent mb-2">
            On This Day ({onThisDay.length} {onThisDay.length === 1 ? 'entry' : 'entries'})
          </h3>
          <div className="space-y-2">
            {(() => {
              let lastYear: number | null = null
              return onThisDay.map((otd: OnThisDayEntry) => {
                const showYear = otd.year !== lastYear
                lastYear = otd.year
                return (
                  <div key={otd.entry.id} className="flex items-center gap-2">
                    <span className="text-xs font-medium text-accent w-10">{showYear ? otd.year : ''}</span>
                    <EntryCard entry={otd.entry} />
                  </div>
                )
              })
            })()}
          </div>
        </div>
      )}

      {isLoading && <div className="text-text-secondary">Loading...</div>}

      <div className="space-y-2">
        {entries.map((entry) => (
          <EntryCard key={entry.id} entry={entry} />
        ))}
      </div>

      <div ref={sentinelRef} className="h-8" />
      {isFetchingNextPage && (
        <div className="text-center text-text-secondary text-sm py-4">Loading more...</div>
      )}
    </div>
  )
}
