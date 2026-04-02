import { apiFetch } from './client'

export interface PlaceType {
  id: number
  name: string
}

export interface Place {
  id: number
  name: string
  place_type: string
  place_type_id: number
  lat: number
  lon: number
  distance_m: number
  date_from: string | null
  date_to: string | null
  notes: string | null
}

export interface PlacesResponse {
  items: Place[]
  total: number
}

export function fetchPlaces(): Promise<PlacesResponse> {
  return apiFetch<PlacesResponse>('/places')
}

export function fetchPlaceTypes(): Promise<PlaceType[]> {
  return apiFetch<PlaceType[]>('/places/types')
}

export function createPlace(data: {
  name: string
  place_type_id: number
  latitude: number
  longitude: number
  distance_m?: number
  date_from?: string | null
  date_to?: string | null
  notes?: string | null
}): Promise<Place> {
  return apiFetch<Place>('/places', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updatePlace(id: number, data: {
  name?: string
  place_type_id?: number
  latitude?: number
  longitude?: number
  distance_m?: number
  date_from?: string | null
  date_to?: string | null
  notes?: string | null
}): Promise<Place> {
  return apiFetch<Place>(`/places/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deletePlace(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/places/${id}`, { method: 'DELETE' })
}

export function syncPlaces(): Promise<Record<string, number>> {
  return apiFetch('/places/sync', { method: 'POST' })
}
