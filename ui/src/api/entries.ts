import { apiFetch } from './client'
import type { EntryDetail, EntryList, Enrichment } from './types'

interface EntryFilters {
  cursor?: string | null
  limit?: number
  journal_id?: number | null
  tag?: string | null
  starred?: boolean | null
  year?: number | null
  month?: number | null
  search?: string | null
}

export function fetchEntries(filters: EntryFilters): Promise<EntryList> {
  const params = new URLSearchParams()
  if (filters.cursor) params.set('cursor', filters.cursor)
  if (filters.limit) params.set('limit', String(filters.limit))
  if (filters.journal_id) params.set('journal_id', String(filters.journal_id))
  if (filters.tag) params.set('tag', filters.tag)
  if (filters.starred !== null && filters.starred !== undefined) params.set('starred', String(filters.starred))
  if (filters.year) params.set('year', String(filters.year))
  if (filters.month) params.set('month', String(filters.month))
  if (filters.search) params.set('search', filters.search)
  const qs = params.toString()
  return apiFetch<EntryList>(`/entries${qs ? `?${qs}` : ''}`)
}

export function fetchEntry(id: number): Promise<EntryDetail> {
  return apiFetch<EntryDetail>(`/entries/${id}`)
}

export function fetchEnrichment(id: number): Promise<Enrichment> {
  return apiFetch<Enrichment>(`/entries/${id}/enrichment`)
}

export function toggleStar(id: number): Promise<{ starred: boolean }> {
  return apiFetch<{ starred: boolean }>(`/entries/${id}/star`, { method: 'PUT' })
}
