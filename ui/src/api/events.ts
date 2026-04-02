import { apiFetch } from './client'
import type { EventDetail, EventsResponse } from './types'

export function fetchEvents(params?: {
  year?: number
  event_type?: string
  trip_id?: number
}): Promise<EventsResponse> {
  const qs = new URLSearchParams()
  if (params?.year) qs.set('year', String(params.year))
  if (params?.event_type) qs.set('event_type', params.event_type)
  if (params?.trip_id) qs.set('trip_id', String(params.trip_id))
  qs.set('limit', '200')
  return apiFetch<EventsResponse>(`/events?${qs}`)
}

export function fetchEvent(id: number): Promise<EventDetail> {
  return apiFetch<EventDetail>(`/events/${id}`)
}

export function createEvent(data: {
  title: string
  event_date: string
  end_date?: string | null
  event_type?: string
  notes?: string | null
  fuzzy_date?: boolean
  latitude?: number | null
  longitude?: number | null
  place_id?: number | null
  trip_id?: number | null
  documents?: { paperless_id: number; label?: string | null }[]
}): Promise<EventDetail> {
  return apiFetch<EventDetail>('/events', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateEvent(
  id: number,
  data: {
    title?: string
    event_date?: string
    end_date?: string | null
    event_type?: string
    notes?: string | null
    fuzzy_date?: boolean
    latitude?: number | null
    longitude?: number | null
    place_id?: number | null
    trip_id?: number | null
  },
): Promise<EventDetail> {
  return apiFetch<EventDetail>(`/events/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteEvent(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/events/${id}`, { method: 'DELETE' })
}

export function linkDocument(
  eventId: number,
  paperlessId: number,
  label?: string | null,
): Promise<{ linked: boolean }> {
  return apiFetch(`/events/${eventId}/documents`, {
    method: 'POST',
    body: JSON.stringify({ paperless_id: paperlessId, label }),
  })
}

export function unlinkDocument(
  eventId: number,
  paperlessId: number,
): Promise<{ unlinked: boolean }> {
  return apiFetch(`/events/${eventId}/documents/${paperlessId}`, {
    method: 'DELETE',
  })
}
