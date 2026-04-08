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
  has_aircraft_image?: boolean
  has_route_image?: boolean
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
  has_aircraft_image?: boolean
  has_route_image?: boolean
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
  reference: string | null
  price: number | null
  currency: string | null
}

export function flightImageUrl(
  flightId: number,
  type: 'aircraft' | 'route',
  size: 'thumb' | 'full',
  ga = false,
): string {
  const prefix = ga ? 'ga-flights' : 'flights'
  return `/api/v1/${prefix}/${flightId}/images/${type}/${size}`
}

export interface OwnershipEntry {
  owner: string
  from: string | null
  to: string | null
  from_display: string
  to_display: string
}

export interface AircraftDetail {
  registration: string
  aircraft_type: string | null
  narrative: string | null
  narrative_model: string | null
  narrative_generated_at: string | null
  has_aircraft_image: boolean
  ownership_timeline: OwnershipEntry[]
  register_url: string | null
  flights: Flight[]
  ga_flights: GaFlight[]
}

export function aircraftImageUrl(registration: string, size: 'thumb' | 'full'): string {
  return `/api/v1/aircraft/${encodeURIComponent(registration)}/image/${size}`
}

export function fetchAircraft(registration: string): Promise<AircraftDetail> {
  return apiFetch<AircraftDetail>(`/aircraft/${encodeURIComponent(registration)}`)
}

// --- Flight detail (full fields from GET /flights/:id) ---
export interface FlightDetail extends Flight {
  dep_icao: string | null
  arr_icao: string | null
  dep_airport_name: string | null
  arr_airport_name: string | null
  airline_code: string | null
  aircraft_code: string | null
  seat_type: number | null
  flight_reason: number | null
  notes: string | null
  gps_matched: boolean | null
  dep_lat: number | null
  dep_lon: number | null
  arr_lat: number | null
  arr_lon: number | null
  gate_origin: string | null
  gate_destination: string | null
  terminal_origin: string | null
  terminal_destination: string | null
  baggage_claim: string | null
  departure_delay: number | null
  arrival_delay: number | null
  codeshares: string | null
  is_route: boolean
  times_flown: number | null
}

export interface FlightUpdate {
  flight_number?: string | null
  airline?: string | null
  aircraft_type?: string | null
  registration?: string | null
  seat_number?: string | null
  seat_type?: number | null
  flight_class?: number | null
  flight_reason?: number | null
  notes?: string | null
  is_route?: boolean
  times_flown?: number | null
}

export interface FlightCreate {
  date: string
  dep_airport: string
  arr_airport: string
  flight_number?: string | null
  airline?: string | null
  aircraft_type?: string | null
  registration?: string | null
  seat_number?: string | null
  seat_type?: number | null
  flight_class?: number | null
  flight_reason?: number | null
  notes?: string | null
  dep_time?: string | null
  arr_time?: string | null
}

export interface GaFlightDetail extends GaFlight {
  hours_sep_pic: number | null
  hours_sep_dual: number | null
  hours_mep_pic: number | null
  hours_mep_dual: number | null
  hours_pic_3: number | null
  hours_dual_3: number | null
  hours_pic_4: number | null
  hours_dual_4: number | null
  hours_instrument: number | null
  hours_as_instructor: number | null
  hours_simulator: number | null
  instructor: string | null
}

export interface GaFlightUpdate {
  aircraft_type?: string | null
  registration?: string | null
  captain?: string | null
  operating_capacity?: string | null
  exercise?: string | null
  comments?: string | null
}

export interface GaFlightCreate {
  date: string
  aircraft_type?: string | null
  registration?: string | null
  captain?: string | null
  operating_capacity?: string | null
  dep_airport?: string | null
  arr_airport?: string | null
  dep_time?: string | null
  arr_time?: string | null
  hours_total?: number | null
  exercise?: string | null
  comments?: string | null
}

export interface RailJourneyUpdate {
  date?: string | null
  time?: string | null
  from_station?: string | null
  from_code?: string | null
  to_station?: string | null
  to_code?: string | null
  operator?: string | null
  ticket_type?: string | null
  direction?: string | null
  train?: string | null
  via?: string | null
  reference?: string | null
  price?: number | null
  currency?: string | null
}

export interface RailJourneyCreate {
  date: string
  time?: string | null
  from_station: string
  from_code?: string | null
  to_station: string
  to_code?: string | null
  operator?: string | null
  ticket_type?: string | null
  direction?: string | null
  train?: string | null
  via?: string | null
  reference?: string | null
  price?: number | null
  currency?: string | null
}

// --- Fetch single items ---
export function fetchFlight(id: number): Promise<FlightDetail> {
  return apiFetch<FlightDetail>(`/flights/${id}`)
}

export function fetchGaFlight(id: number): Promise<GaFlightDetail> {
  return apiFetch<GaFlightDetail>(`/ga-flights/${id}`)
}

export function fetchRailJourney(id: number): Promise<RailJourney> {
  return apiFetch<RailJourney>(`/rail-journeys/${id}`)
}

// --- Create ---
export function createFlight(data: FlightCreate): Promise<FlightDetail> {
  return apiFetch('/flights', { method: 'POST', body: JSON.stringify(data) })
}

export function createGaFlight(data: GaFlightCreate): Promise<GaFlightDetail> {
  return apiFetch('/ga-flights', { method: 'POST', body: JSON.stringify(data) })
}

export function createRailJourney(data: RailJourneyCreate): Promise<RailJourney> {
  return apiFetch('/rail-journeys', { method: 'POST', body: JSON.stringify(data) })
}

// --- Update ---
export function updateFlight(id: number, data: FlightUpdate): Promise<FlightDetail> {
  return apiFetch(`/flights/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function updateGaFlight(id: number, data: GaFlightUpdate): Promise<GaFlightDetail> {
  return apiFetch(`/ga-flights/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function updateRailJourney(id: number, data: RailJourneyUpdate): Promise<RailJourney> {
  return apiFetch(`/rail-journeys/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

// --- Delete ---
export function deleteFlight(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/flights/${id}`, { method: 'DELETE' })
}

export function deleteGaFlight(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/ga-flights/${id}`, { method: 'DELETE' })
}

export function deleteRailJourney(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/rail-journeys/${id}`, { method: 'DELETE' })
}

// --- List ---
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
