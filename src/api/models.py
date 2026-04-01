"""Pydantic response models."""

from datetime import datetime

from pydantic import BaseModel


class JournalOut(BaseModel):
    id: int
    name: str
    color_hex: int | None = None
    description: str | None = None
    entry_count: int = 0


class TagOut(BaseModel):
    id: int
    name: str
    entry_count: int = 0


class LocationOut(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    place_name: str | None = None
    address: str | None = None
    locality: str | None = None
    admin_area: str | None = None
    country: str | None = None
    place_id: int | None = None
    place_label: str | None = None
    location_type: str | None = None


class WeatherOut(BaseModel):
    temp_celsius: float | None = None
    conditions: str | None = None
    weather_code: str | None = None
    relative_humidity: float | None = None
    wind_speed_kph: float | None = None
    pressure_mb: float | None = None
    visibility_km: float | None = None
    moon_phase: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None
    location_id: int | None = None


class MusicTrackOut(BaseModel):
    track: str | None = None
    artist: str | None = None
    album: str | None = None
    album_year: int | None = None
    played_at: datetime | None = None
    source: str = "dayone"
    recording_mbid: str | None = None
    artist_mbid: str | None = None
    spotify_track_id: str | None = None


class MusicOut(BaseModel):
    track: str | None = None
    artist: str | None = None
    album: str | None = None
    album_year: int | None = None


class AttachmentOut(BaseModel):
    id: int
    uuid: str | None = None
    type: str
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    caption: str | None = None
    duration: float | None = None
    is_favorite: bool = False
    camera_make: str | None = None
    camera_model: str | None = None
    date: datetime | None = None
    media_url: str | None = None
    immich_asset_id: str | None = None
    immich_url: str | None = None


class EntrySummary(BaseModel):
    id: int
    uuid: str
    journal_id: int | None = None
    journal_name: str | None = None
    created_at: datetime
    starred: bool = False
    pinned: bool = False
    entry_type: str = "diary"
    parent_entry_id: int | None = None
    child_count: int = 0
    text_preview: str | None = None
    location: LocationOut | None = None
    weather: WeatherOut | None = None
    music: MusicOut | None = None
    tags: list[str] = []
    attachment_count: int = 0
    thumbnail_url: str | None = None


class ChildEntrySummary(BaseModel):
    id: int
    uuid: str
    created_at: datetime
    text_preview: str | None = None
    mood: int | None = None
    energy: int | None = None
    attachment_count: int = 0


class EntryDetail(BaseModel):
    id: int
    uuid: str
    journal_id: int | None = None
    journal_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    markdown_text: str | None = None
    rich_text_json: dict | None = None
    starred: bool = False
    pinned: bool = False
    is_draft: bool = False
    is_all_day: bool = False
    duration: int = 0
    device_name: str | None = None
    device_model: str | None = None
    timezone: str | None = None
    retrospective: str | None = None
    retrospective_at: datetime | None = None
    entry_type: str = "diary"
    mood: int | None = None
    energy: int | None = None
    parent_entry_id: int | None = None
    prev_entry_id: int | None = None
    next_entry_id: int | None = None
    location: LocationOut | None = None
    locations: list[LocationOut] = []
    weather: WeatherOut | None = None
    weathers: list[WeatherOut] = []
    music: MusicOut | None = None
    music_tracks: list[MusicTrackOut] = []
    tags: list[str] = []
    attachments: list[AttachmentOut] = []
    children: list[ChildEntrySummary] = []


class EntryList(BaseModel):
    items: list[EntrySummary]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None


class CalendarDay(BaseModel):
    day: int
    entry_id: int


class CalendarMonth(BaseModel):
    year: int
    month: int
    entry_count: int
    days: list[int] = []
    day_entries: list[CalendarDay] = []


class OnThisDayEntry(BaseModel):
    year: int
    entry: EntrySummary


class MapEntry(BaseModel):
    id: int
    uuid: str
    created_at: datetime
    text_preview: str | None = None
    latitude: float
    longitude: float
    place_name: str | None = None
    thumbnail_url: str | None = None


class StatsOut(BaseModel):
    total_entries: int = 0
    total_photos: int = 0
    total_videos: int = 0
    total_tags: int = 0
    total_journals: int = 0
    entries_with_location: int = 0
    entries_with_weather: int = 0
    entries_with_music: int = 0
    starred_entries: int = 0
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    entries_by_year: dict[int, int] = {}
    top_tags: list[TagOut] = []
    top_locations: list[dict] = []


class EntryUpdate(BaseModel):
    markdown_text: str | None = None
    tags: list[str] | None = None
    retrospective: str | None = None
    mood: int | None = None       # 1-5, 0 to clear
    energy: int | None = None     # 1-5, 0 to clear


class LocationCreate(BaseModel):
    latitude: float
    longitude: float
    altitude: float | None = None
    place_name: str | None = None
    address: str | None = None
    locality: str | None = None
    admin_area: str | None = None
    country: str | None = None


class WeatherCreate(BaseModel):
    temp_celsius: float | None = None
    conditions: str | None = None
    weather_code: str | None = None
    relative_humidity: float | None = None
    wind_speed_kph: float | None = None
    wind_bearing: float | None = None
    pressure_mb: float | None = None
    visibility_km: float | None = None


class MusicCreate(BaseModel):
    track: str | None = None
    artist: str | None = None
    album: str | None = None
    album_year: int | None = None


class EntryCreate(BaseModel):
    markdown_text: str = ""
    journal_id: int | None = None
    tags: list[str] = []
    starred: bool = False
    timezone: str | None = None
    retrospective: str | None = None
    location: LocationCreate | None = None
    weather: WeatherCreate | None = None
    music: MusicCreate | None = None
    immich_asset_ids: list[str] = []


class ImmichAttachRequest(BaseModel):
    immich_asset_ids: list[str]


class UserOut(BaseModel):
    email: str
    display_name: str
    role: str
