import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchEntries } from '../api/entries'

interface EntryFilters {
  journal_id?: number | null
  tag?: string | null
  starred?: boolean | null
  year?: number | null
  month?: number | null
  search?: string | null
}

export function useEntries(filters: EntryFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['entries', filters],
    queryFn: ({ pageParam }) =>
      fetchEntries({ ...filters, cursor: pageParam ?? null, limit: 50 }),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
    initialPageParam: null as string | null,
  })
}
