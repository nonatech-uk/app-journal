import { apiFetch } from './client'

export interface Activity {
  id: number
  activity_type: string
  title: string | null
  date: string | null
  start_time: string | null
  distance_km: number | null
  duration_seconds: number | null
  moving_time_seconds: number | null
  elevation_gain: number | null
  elevation_loss: number | null
  max_altitude: number | null
  avg_speed_kmh: number | null
  max_speed_kmh: number | null
  avg_heartrate: number | null
  max_heartrate: number | null
  calories: number | null
  conditions: string | null
  notes: string | null
  source: string
  strava_activity_id: number | null
  entry_id: number | null
}

export interface ActivitiesResponse {
  items: Activity[]
  total: number
  years: { year: number; count: number }[]
  types: { type: string; count: number }[]
}

export function fetchActivities(year?: number, activityType?: string): Promise<ActivitiesResponse> {
  const params = new URLSearchParams({ limit: '500' })
  if (year) params.set('year', String(year))
  if (activityType) params.set('activity_type', activityType)
  return apiFetch<ActivitiesResponse>(`/activities?${params}`)
}

export function fetchActivity(id: number): Promise<Activity> {
  return apiFetch<Activity>(`/activities/${id}`)
}

export function createActivity(data: Record<string, unknown>): Promise<{ id: number }> {
  return apiFetch('/activities', { method: 'POST', body: JSON.stringify(data) })
}

export function updateActivity(id: number, data: Record<string, unknown>): Promise<{ updated: boolean }> {
  return apiFetch(`/activities/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteActivity(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/activities/${id}`, { method: 'DELETE' })
}

export function linkActivity(entryId: number, activityId: number): Promise<{ linked: boolean }> {
  return apiFetch(`/entries/${entryId}/activities/${activityId}/link`, { method: 'POST' })
}

export function unlinkActivity(entryId: number, activityId: number): Promise<{ unlinked: boolean }> {
  return apiFetch(`/entries/${entryId}/activities/${activityId}/link`, { method: 'DELETE' })
}
