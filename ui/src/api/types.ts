export interface Location {
  latitude: number | null
  longitude: number | null
  altitude?: number | null
  place_name: string | null
  address?: string | null
  locality: string | null
  admin_area: string | null
  country: string | null
}

export interface Weather {
  temp_celsius: number | null
  conditions: string | null
  weather_code?: string | null
  relative_humidity?: number | null
  wind_speed_kph?: number | null
  pressure_mb?: number | null
  visibility_km?: number | null
  moon_phase?: number | null
  sunrise?: string | null
  sunset?: string | null
}

export interface Music {
  track: string | null
  artist: string | null
  album: string | null
  album_year?: number | null
}

export interface Attachment {
  id: number
  uuid: string | null
  type: string
  filename: string | null
  width: number | null
  height: number | null
  caption: string | null
  duration: number | null
  is_favorite: boolean
  camera_make: string | null
  camera_model: string | null
  date: string | null
  media_url: string | null
  immich_asset_id: string | null
  immich_url: string | null
}

export interface EntrySummary {
  id: number
  uuid: string
  journal_id: number | null
  journal_name: string | null
  created_at: string
  starred: boolean
  pinned: boolean
  text_preview: string | null
  location: Location | null
  weather: Weather | null
  music: Music | null
  tags: string[]
  attachment_count: number
  thumbnail_url: string | null
}

export interface EntryDetail extends EntrySummary {
  modified_at: string | null
  markdown_text: string | null
  rich_text_json: Record<string, unknown> | null
  is_draft: boolean
  is_all_day: boolean
  duration: number
  device_name: string | null
  device_model: string | null
  timezone: string | null
  retrospective: string | null
  retrospective_at: string | null
  entry_type: string
  mood: number | null
  energy: number | null
  attachments: Attachment[]
}

export interface EntryList {
  items: EntrySummary[]
  next_cursor: string | null
  has_more: boolean
  total: number | null
}

export interface Journal {
  id: number
  name: string
  color_hex: number | null
  description: string | null
  entry_count: number
}

export interface Tag {
  id: number
  name: string
  entry_count: number
}

export interface CalendarMonth {
  year: number
  month: number
  entry_count: number
  days: number[]
}

export interface OnThisDayEntry {
  year: number
  entry: EntrySummary
}

export interface MapEntry {
  id: number
  uuid: string
  created_at: string
  text_preview: string | null
  latitude: number
  longitude: number
  place_name: string | null
  thumbnail_url: string | null
}

export interface Stats {
  total_entries: number
  total_photos: number
  total_videos: number
  total_tags: number
  total_journals: number
  entries_with_location: number
  entries_with_weather: number
  entries_with_music: number
  starred_entries: number
  date_range_start: string | null
  date_range_end: string | null
  entries_by_year: Record<number, number>
  top_tags: Tag[]
  top_locations: { country: string; locality: string; count: number }[]
}

export interface User {
  email: string
  display_name: string
  role: string
}

export interface EnrichmentFlight {
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
  linked: boolean
}

export interface EnrichmentSkiing {
  id: number
  date: string
  location: string | null
  duration_hours: number | null
  distance_km: number | null
  vertical_up_m: number | null
  vertical_down_m: number | null
  max_speed_kmh: number | null
  max_altitude_m: number | null
  num_runs: number | null
  num_lifts: number | null
  season: string | null
  linked: boolean
}

export interface Enrichment {
  scrobbles: { id: number; artist: string; track: string; album: string; listened_at: string; linked: boolean }[]
  transactions: { merchant_name: string; amount: number; currency: string; posted_at: string; category: string }[]
  gps_summary: { city: string; country: string; date: string } | null
  tautulli_watches: { title: string; media_type: string }[]
  flights: EnrichmentFlight[]
  skiing: EnrichmentSkiing[]
  watches: {
    title: string
    media_type: string
    series_title: string | null
    season: number | null
    episode: number | null
    year: number | null
    reference_id: number | string | null
    watched_at: number | null
    platform: string | null
    percent_complete: number | null
    linked: boolean
  }[]
}

export interface ContextLocation {
  latitude: number
  longitude: number
  timestamp: string
  place_name: string | null
  locality: string | null
  admin_area: string | null
  country: string | null
}

export interface ContextWeather {
  temp_celsius: number | null
  conditions: string | null
  weather_code: string | null
  relative_humidity: number | null
  wind_speed_kph: number | null
  wind_bearing: number | null
  pressure_mb: number | null
}

export interface ContextScrobble {
  artist: string
  track: string
  album: string | null
  listened_at: string
}

export interface ContextWatch {
  title: string
  media_type: string
  year: number | null
  watched_at: number | null
}

export interface EntryContext {
  location: ContextLocation | null
  weather: ContextWeather | null
  scrobbles: ContextScrobble[]
  tautulli_watches: ContextWatch[]
  timestamp: string
}

export interface ImmichAsset {
  id: string
  type: string
  original_filename: string | null
  created_at: string | null
  thumbnail_url: string
}

export interface EntryCreatePayload {
  markdown_text: string
  journal_id?: number | null
  tags: string[]
  starred: boolean
  timezone?: string | null
  location?: {
    latitude: number
    longitude: number
    altitude?: number | null
    place_name?: string | null
    address?: string | null
    locality?: string | null
    admin_area?: string | null
    country?: string | null
  } | null
  weather?: {
    temp_celsius?: number | null
    conditions?: string | null
    weather_code?: string | null
    relative_humidity?: number | null
    wind_speed_kph?: number | null
    wind_bearing?: number | null
    pressure_mb?: number | null
  } | null
  music?: {
    track?: string | null
    artist?: string | null
    album?: string | null
  } | null
  immich_asset_ids: string[]
}
