import { apiFetch } from './client'

interface ListResponse<T> {
  items: T[]
  total: number
  years: { year: number; count: number }[]
}

export interface Flight {
  id: number
  date: string
  flight_number: string | null
  dep_airport: string
  dep_airport_name: string | null
  arr_airport: string
  arr_airport_name: string | null
  dep_time: string | null
  arr_time: string | null
  duration: string | null
  airline: string | null
  aircraft_type: string | null
  registration: string | null
  seat_number: string | null
  flight_class: number | null
  distance_km: number | null
  source: string | null
}

export interface GaFlight {
  id: number
  date: string
  aircraft_type: string | null
  registration: string | null
  captain: string | null
  operating_capacity: string | null
  dep_airport: string | null
  arr_airport: string | null
  dep_time: string | null
  arr_time: string | null
  hours_total: number | null
  exercise: string | null
  comments: string | null
}

export interface RailJourney {
  id: number
  date: string
  time: string | null
  from_station: string
  from_code: string | null
  to_station: string
  to_code: string | null
  operator: string | null
  ticket_type: string | null
  direction: string | null
  train: string | null
  via: string | null
  price: number | null
  currency: string | null
}

export function fetchFlights(year?: number): Promise<ListResponse<Flight>> {
  const params = year ? `?year=${year}&limit=500` : '?limit=500'
  return apiFetch<ListResponse<Flight>>(`/flights${params}`)
}

export function fetchGaFlights(year?: number): Promise<ListResponse<GaFlight>> {
  const params = year ? `?year=${year}&limit=500` : '?limit=500'
  return apiFetch<ListResponse<GaFlight>>(`/ga-flights${params}`)
}

export function fetchRailJourneys(year?: number): Promise<ListResponse<RailJourney>> {
  const params = year ? `?year=${year}&limit=500` : '?limit=500'
  return apiFetch<ListResponse<RailJourney>>(`/rail-journeys${params}`)
}
