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

export interface Enrichment {
  scrobbles: { artist: string; track: string; album: string; scrobbled_at: string }[]
  transactions: { merchant_name: string; amount: number; currency: string; posted_at: string; category: string }[]
  gps_summary: { city: string; country: string; date: string } | null
  tautulli_watches: { title: string; media_type: string }[]
}
