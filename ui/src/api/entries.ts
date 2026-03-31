import { apiFetch } from './client'
import type { EntryDetail, EntryList, Enrichment, EntryContext, EntryCreatePayload, ImmichAsset } from './types'

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

export function updateEntry(id: number, data: { markdown_text?: string; tags?: string[]; retrospective?: string; mood?: number; energy?: number }): Promise<EntryDetail> {
  return apiFetch<EntryDetail>(`/entries/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function deleteEntry(id: number): Promise<void> {
  return apiFetch(`/entries/${id}`, { method: 'DELETE' })
}

export function fetchContext(): Promise<EntryContext> {
  return apiFetch<EntryContext>('/context/now')
}

export function createEntry(data: EntryCreatePayload): Promise<EntryDetail> {
  return apiFetch<EntryDetail>('/entries', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function uploadVoiceNote(entryId: number, audio: Blob): Promise<EntryDetail> {
  const form = new FormData()
  form.append('audio', audio, 'voice.webm')
  return fetch(`/api/v1/entries/${entryId}/voice`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  }).then(async (res) => {
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  })
}

export function searchImmich(query: string, limit = 20): Promise<ImmichAsset[]> {
  return apiFetch<ImmichAsset[]>(`/immich/search?q=${encodeURIComponent(query)}&limit=${limit}`)
}

export function attachImmichPhotos(entryId: number, assetIds: string[]): Promise<EntryDetail> {
  return apiFetch<EntryDetail>(`/entries/${entryId}/attachments/immich`, {
    method: 'POST',
    body: JSON.stringify({ immich_asset_ids: assetIds }),
  })
}

export function searchImmichRecent(days = 7, limit = 20): Promise<ImmichAsset[]> {
  return apiFetch<ImmichAsset[]>(`/immich/search/recent?days=${days}&limit=${limit}`)
}

export function linkFlight(entryId: number, flightId: number, flightType = 'commercial'): Promise<{ linked: boolean }> {
  return apiFetch(`/entries/${entryId}/flights`, {
    method: 'POST',
    body: JSON.stringify({ flight_id: flightId, flight_type: flightType }),
  })
}

export function unlinkFlight(entryId: number, flightId: number, flightType = 'commercial'): Promise<{ unlinked: boolean }> {
  return apiFetch(`/entries/${entryId}/flights/${flightId}?flight_type=${flightType}`, {
    method: 'DELETE',
  })
}

export function linkSkiingDay(entryId: number, skiingDayId: number, location?: string): Promise<{ linked: boolean; activity_id?: number }> {
  return apiFetch(`/entries/${entryId}/activities/skiing`, {
    method: 'POST',
    body: JSON.stringify({ skiing_day_id: skiingDayId, location }),
  })
}

export function unlinkActivity(entryId: number, activityId: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/entries/${entryId}/activities/${activityId}`, {
    method: 'DELETE',
  })
}

export function importScrobbles(entryId: number, scrobbleIds: number[]): Promise<{ imported: number }> {
  return apiFetch(`/entries/${entryId}/import-scrobbles`, {
    method: 'POST',
    body: JSON.stringify({ scrobble_ids: scrobbleIds }),
  })
}

export function importAllScrobbles(entryId: number): Promise<{ imported: number; total_in_window: number }> {
  return apiFetch(`/entries/${entryId}/import-all-scrobbles`, {
    method: 'POST',
  })
}

export function importAllWatches(entryId: number): Promise<{ imported: number; total_on_date: number }> {
  return apiFetch(`/entries/${entryId}/import-all-watches`, {
    method: 'POST',
  })
}

export interface PersonSummary {
  id: number
  name: string
  nickname: string | null
  role?: string | null
  entry_count?: number
}

export function fetchEntryPeople(entryId: number): Promise<PersonSummary[]> {
  return apiFetch<PersonSummary[]>(`/entries/${entryId}/people`)
}

export function searchPeople(q: string): Promise<PersonSummary[]> {
  return apiFetch<PersonSummary[]>(`/people?q=${encodeURIComponent(q)}`)
}

export function linkPerson(entryId: number, personId: number, role?: string): Promise<{ linked: boolean }> {
  return apiFetch(`/entries/${entryId}/people`, {
    method: 'POST',
    body: JSON.stringify({ person_id: personId, role }),
  })
}

export function unlinkPerson(entryId: number, personId: number): Promise<{ unlinked: boolean }> {
  return apiFetch(`/entries/${entryId}/people/${personId}`, { method: 'DELETE' })
}

export function createPerson(name: string): Promise<{ id: number; name: string }> {
  return apiFetch('/people', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function deleteAttachment(entryId: number, attachmentId: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/entries/${entryId}/attachments/${attachmentId}`, { method: 'DELETE' })
}

export function uploadAttachment(entryId: number, file: File): Promise<EntryDetail> {
  const form = new FormData()
  form.append('file', file)
  return fetch(`/api/v1/entries/${entryId}/attachments/upload`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  }).then(async (res) => {
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  })
}
