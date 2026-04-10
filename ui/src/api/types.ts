export interface Location {
  latitude: number | null
  longitude: number | null
  altitude?: number | null
  place_name: string | null
  address?: string | null
  locality: string | null
  admin_area: string | null
  country: string | null
  place_id: number | null
  place_label: string | null
  location_type?: string | null
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
  location_id?: number | null
}

export interface Music {
  track: string | null
  artist: string | null
  album: string | null
  album_year?: number | null
}

export interface MusicTrack {
  track: string | null
  artist: string | null
  album: string | null
  album_year: number | null
  played_at: string | null
  source: string
  recording_mbid: string | null
  artist_mbid: string | null
  spotify_track_id: string | null
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
  prev_entry_id: number | null
  next_entry_id: number | null
  locations: Location[]
  weathers: Weather[]
  music_tracks: MusicTrack[]
  attachments: Attachment[]
  events: { id: number; title: string; event_type: string; event_date: string; end_date: string | null; place_label: string | null }[]
  activities: {
    id: number
    activity_type: string
    title: string | null
    activity_date: string | null
    start_time: string | null
    distance_km: number | null
    duration_seconds: number | null
    moving_time_seconds: number | null
    elevation_gain: number | null
    source: string
    strava_activity_id: number | null
    has_track: boolean
    track_svg_url: string | null
  }[]
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

export interface CalendarDay {
  day: number
  entry_id: number
}

export interface CalendarMonth {
  year: number
  month: number
  entry_count: number
  days: number[]
  day_entries: CalendarDay[]
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

export interface EnrichmentActivity {
  id: number
  activity_type: string
  title: string | null
  date: string | null
  start_time: string | null
  distance_km: number | null
  duration_seconds: number | null
  moving_time_seconds: number | null
  elevation_gain: number | null
  avg_speed_kmh: number | null
  avg_heartrate: number | null
  calories: number | null
  source: string
  strava_activity_id: number | null
  linked: boolean
}

export interface Enrichment {
  scrobbles: { id: number; artist: string; track: string; album: string; listened_at: string; linked: boolean }[]
  transactions: { merchant_name: string; amount: number; currency: string; posted_at: string; category: string }[]
  gps_summary: { city: string; country: string; date: string } | null
  gps_track: {
    point_count: number
    start_place: string | null
    end_place: string | null
    start_place_type: string | null
    end_place_type: string | null
    track_url: string | null
    track_svg_url: string | null
  } | null
  tautulli_watches: { title: string; media_type: string }[]
  flights: EnrichmentFlight[]
  rail_journeys: {
    id: number
    date: string
    time: string | null
    from_station: string
    from_code: string | null
    to_station: string
    to_code: string | null
    operator: string | null
    train: string | null
    via: string | null
    linked: boolean
  }[]
  skiing: EnrichmentSkiing[]
  activities: EnrichmentActivity[]
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
    rating_key: number | null
    linked: boolean
  }[]
  events: {
    id: number
    title: string
    event_type: string
    event_date: string
    end_date: string | null
    place_label: string | null
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

// Events
export interface EventSummary {
  id: number
  title: string
  event_date: string
  end_date: string | null
  event_type: string
  event_type_id: number
  notes: string | null
  fuzzy_date: boolean
  latitude: number | null
  longitude: number | null
  place_id: number | null
  place_label: string | null
  trip_id: number | null
  trip_title: string | null
}

export interface EventDocument {
  paperless_id: number
  label: string | null
}

export interface EventDetail extends EventSummary {
  documents: EventDocument[]
  created_at: string
  modified_at: string
}

export interface EventsResponse {
  items: EventSummary[]
  total: number
  years: { year: number; count: number }[]
  types: { type: string; count: number }[]
}


// ---------------------------------------------------------------------------
// Memoirs
// ---------------------------------------------------------------------------

export interface MemoirSummary {
  id: number
  parent_id: number | null
  title: string
  start_year: number | null
  start_month: number | null
  end_year: number | null
  end_month: number | null
  date_label: string | null
  description: string | null
  entry_id: number | null
  cover_asset_id: string | null
  sort_order: number
  created_at: string
  modified_at: string
  ghost_post_id: string | null
  ghost_status: string | null
  ghost_visibility: string | null
  ghost_published_at: string | null
  tags: string[]
  featured: boolean
  slug: string | null
  meta_description: string | null
  child_count: number
  attachment_count: number
}

export interface MemoirAttachment {
  id: number
  uuid: string | null
  type: string
  filename: string | null
  file_size: number | null
  width: number | null
  height: number | null
  caption: string | null
  transcription: string | null
  media_url: string
  thumbnail_url: string
  immich_asset_id: string | null
}

export interface MemoirLinkedEntry {
  id: number
  uuid: string
  created_at: string
  preview: string | null
  place_name: string | null
}

export interface MemoirDetail extends MemoirSummary {
  markdown_text: string | null
  attachments: MemoirAttachment[]
  children: MemoirSummary[]
  linked_entries: MemoirLinkedEntry[]
  parent: { id: number; title: string } | null
}

export interface MemoirsResponse {
  items: MemoirSummary[]
  total: number
}
