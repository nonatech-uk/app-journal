import { apiFetch } from './client'
import type { CalendarMonth, Journal, MapEntry, OnThisDayEntry, Stats, Tag, User, EntryList } from './types'

export function fetchJournals(): Promise<Journal[]> {
  return apiFetch<Journal[]>('/journals')
}

export function fetchTags(): Promise<Tag[]> {
  return apiFetch<Tag[]>('/tags')
}

export function fetchCalendar(): Promise<CalendarMonth[]> {
  return apiFetch<CalendarMonth[]>('/calendar')
}

export function fetchOnThisDay(month?: number, day?: number): Promise<OnThisDayEntry[]> {
  const params = new URLSearchParams()
  if (month) params.set('month', String(month))
  if (day) params.set('day', String(day))
  const qs = params.toString()
  return apiFetch<OnThisDayEntry[]>(`/on-this-day${qs ? `?${qs}` : ''}`)
}

export function fetchMapEntries(year?: number, journal_id?: number): Promise<MapEntry[]> {
  const params = new URLSearchParams()
  if (year) params.set('year', String(year))
  if (journal_id) params.set('journal_id', String(journal_id))
  const qs = params.toString()
  return apiFetch<MapEntry[]>(`/map/entries${qs ? `?${qs}` : ''}`)
}

export function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>('/stats')
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/auth/me')
}

export function searchEntries(q: string, limit?: number, offset?: number): Promise<EntryList> {
  const params = new URLSearchParams({ q })
  if (limit) params.set('limit', String(limit))
  if (offset) params.set('offset', String(offset))
  return apiFetch<EntryList>(`/search?${params}`)
}
