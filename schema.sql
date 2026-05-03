-- Journal app schema — PostgreSQL

CREATE TABLE IF NOT EXISTS app_user (
    email       text PRIMARY KEY,
    display_name text NOT NULL DEFAULT '',
    role        text NOT NULL DEFAULT 'admin'  -- admin | readonly
);

INSERT INTO app_user (email, display_name, role)
VALUES ('stu@mees.st', 'Stu', 'admin')
ON CONFLICT DO NOTHING;


CREATE TABLE IF NOT EXISTS journal (
    id          serial PRIMARY KEY,
    dayone_pk   integer UNIQUE,
    name        text NOT NULL,
    color_hex   integer,
    description text,
    is_trash    boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS entry (
    id              serial PRIMARY KEY,
    uuid            text UNIQUE NOT NULL,
    journal_id      integer REFERENCES journal(id),
    created_at      timestamptz NOT NULL,
    modified_at     timestamptz,
    markdown_text   text,
    rich_text_json  jsonb,
    starred         boolean NOT NULL DEFAULT false,
    pinned          boolean NOT NULL DEFAULT false,
    is_draft        boolean NOT NULL DEFAULT false,
    is_all_day      boolean NOT NULL DEFAULT false,
    duration        bigint DEFAULT 0,
    device_name     text,
    device_model    text,
    device_type     text,
    timezone        text,
    gregorian_year  integer,
    gregorian_month integer,
    gregorian_day   integer,
    search_vector   tsvector,
    retrospective   text,
    retrospective_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_entry_created_at ON entry (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entry_journal_id ON entry (journal_id);
CREATE INDEX IF NOT EXISTS idx_entry_search ON entry USING gin(search_vector);
CREATE INDEX IF NOT EXISTS idx_entry_year_month ON entry (gregorian_year, gregorian_month);
CREATE INDEX IF NOT EXISTS idx_entry_starred ON entry (starred) WHERE starred = true;

-- Auto-update search vector
CREATE OR REPLACE FUNCTION entry_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', coalesce(NEW.markdown_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_entry_search ON entry;
CREATE TRIGGER trg_entry_search
    BEFORE INSERT OR UPDATE OF markdown_text ON entry
    FOR EACH ROW EXECUTE FUNCTION entry_search_trigger();


CREATE TABLE IF NOT EXISTS attachment (
    id              serial PRIMARY KEY,
    entry_id        integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    uuid            text,
    type            text NOT NULL,          -- jpeg, png, mov, mp4, pdf
    filename        text,
    file_size       integer,
    width           integer,
    height          integer,
    order_in_entry  integer DEFAULT 0,
    caption         text,
    duration        float,
    is_favorite     boolean NOT NULL DEFAULT false,
    camera_make     text,
    camera_model    text,
    lens_model      text,
    iso             integer,
    f_number        text,
    focal_length    text,
    transcription   text,
    date            timestamptz,
    local_path      text                    -- relative path under media_root
);

CREATE INDEX IF NOT EXISTS idx_attachment_entry_id ON attachment (entry_id);
CREATE INDEX IF NOT EXISTS idx_attachment_type ON attachment (type);

-- Immich provenance tracking
ALTER TABLE attachment ADD COLUMN IF NOT EXISTS immich_asset_id text;
CREATE INDEX IF NOT EXISTS idx_attachment_immich ON attachment (immich_asset_id) WHERE immich_asset_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS location (
    id              serial PRIMARY KEY,
    entry_id        integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE UNIQUE,
    latitude        double precision,
    longitude       double precision,
    altitude        double precision,
    heading         double precision,
    speed           double precision,
    place_name      text,
    address         text,
    locality        text,
    admin_area      text,
    country         text,
    timezone_name   text,
    user_label      text,
    place_id        integer,
    place_label     text
);

CREATE INDEX IF NOT EXISTS idx_location_coords ON location (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_location_entry_id ON location (entry_id);


CREATE TABLE IF NOT EXISTS weather (
    id                  serial PRIMARY KEY,
    entry_id            integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    temp_celsius        float,
    conditions          text,
    weather_code        text,
    relative_humidity   float,
    wind_speed_kph      float,
    wind_bearing        float,
    wind_chill_celsius  float,
    pressure_mb         float,
    visibility_km       float,
    moon_phase          float,
    moon_phase_code     text,
    sunrise             timestamptz,
    sunset              timestamptz,
    location_id         integer REFERENCES location(id) ON DELETE SET NULL,
    sequence_order      integer DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_weather_entry_id ON weather (entry_id);
CREATE INDEX IF NOT EXISTS idx_weather_location_id ON weather (location_id);


CREATE TABLE IF NOT EXISTS music (
    id          serial PRIMARY KEY,
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE UNIQUE,
    track       text,
    artist      text,
    album       text,
    album_year  integer
);

CREATE INDEX IF NOT EXISTS idx_music_entry_id ON music (entry_id);


CREATE TABLE IF NOT EXISTS tag (
    id      serial PRIMARY KEY,
    name    text UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS entry_tag (
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    tag_id      integer NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_entry_tag_tag_id ON entry_tag (tag_id);


-- ============================================================
-- Phase 1: Schema extensions for Personal Intelligence Fabric
-- ============================================================

-- 1a. entry_flight — bridge to mylocation.flights / ga_flights (cross-DB, no enforced FK)
CREATE TABLE IF NOT EXISTS entry_flight (
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    flight_id   integer NOT NULL,
    flight_type text NOT NULL DEFAULT 'commercial',  -- 'commercial' | 'ga'
    PRIMARY KEY (entry_id, flight_id, flight_type)
);

-- 1b. activity — links entries to skiing days and other tracked activities
CREATE TABLE IF NOT EXISTS activity (
    id                serial PRIMARY KEY,
    entry_id          integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    activity_type     text NOT NULL,          -- 'skiing', 'hiking', 'cycling', 'running', etc.
    title             text,
    skiing_day_id     integer,                -- references mylocation.skiing_days.id (app-layer)
    distance_km       float,
    duration_seconds  integer,
    elevation_gain    float,
    elevation_loss    float,
    max_altitude      float,
    guide             text,
    partners          text[],
    conditions        text,
    notes             text
);

CREATE INDEX IF NOT EXISTS idx_activity_entry_id ON activity (entry_id);
CREATE INDEX IF NOT EXISTS idx_activity_type ON activity (activity_type);

-- 1c. music table extensions — multiple tracks per entry, scrobble linkage
ALTER TABLE music ADD COLUMN IF NOT EXISTS played_at timestamptz;
ALTER TABLE music ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'dayone';  -- 'dayone' | 'scrobble' | 'manual'
ALTER TABLE music ADD COLUMN IF NOT EXISTS scrobble_db_id integer;
ALTER TABLE music ADD COLUMN IF NOT EXISTS play_count integer;

-- Drop the UNIQUE constraint on music.entry_id to allow multiple tracks per entry.
-- The constraint name is "music_entry_id_key" (PostgreSQL auto-generated).
-- We wrap in DO block so it's idempotent.
DO $$
BEGIN
    ALTER TABLE music DROP CONSTRAINT IF EXISTS music_entry_id_key;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_music_scrobble_unique
    ON music (entry_id, scrobble_db_id) WHERE scrobble_db_id IS NOT NULL;

-- 1c-ii. music metadata enrichment columns — cross-DB FKs to scrobble.music_artist / music_recording
ALTER TABLE music ADD COLUMN IF NOT EXISTS recording_mbid uuid;
ALTER TABLE music ADD COLUMN IF NOT EXISTS artist_mbid uuid;
CREATE INDEX IF NOT EXISTS idx_music_recording_mbid ON music (recording_mbid) WHERE recording_mbid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_music_artist_mbid ON music (artist_mbid) WHERE artist_mbid IS NOT NULL;
ALTER TABLE music ADD COLUMN IF NOT EXISTS spotify_track_id text;

-- 1d. media_watch — Plex/Tautulli watch history linked to entries
CREATE TABLE IF NOT EXISTS media_watch (
    id                  serial PRIMARY KEY,
    entry_id            integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    title               text NOT NULL,
    media_type          text NOT NULL,        -- 'movie' | 'episode' | 'track'
    series_title        text,
    season              integer,
    episode             integer,
    platform            text DEFAULT 'plex',
    rating              float,
    notes               text,
    tautulli_session_key text,
    watched_at          timestamptz
);

CREATE INDEX IF NOT EXISTS idx_media_watch_entry_id ON media_watch (entry_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_media_watch_tautulli_unique
    ON media_watch (entry_id, tautulli_session_key) WHERE tautulli_session_key IS NOT NULL;

-- 1e. trip schema (ltree hierarchy)
CREATE EXTENSION IF NOT EXISTS ltree;

CREATE TABLE IF NOT EXISTS trip (
    id              serial PRIMARY KEY,
    path            ltree NOT NULL,
    title           text NOT NULL,
    description     text,
    start_date      date,
    end_date        date,
    countries       text[],
    locations       text[],
    companions      text[],
    cover_asset_id  text,               -- immich asset ID for cover photo
    immich_album_id text,               -- link back to source Immich album
    tags            text[],
    notes           text,
    custom_stats    jsonb DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    modified_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trip_path ON trip USING gist (path);
CREATE INDEX IF NOT EXISTS idx_trip_dates ON trip (start_date, end_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trip_immich_album ON trip (immich_album_id) WHERE immich_album_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS trip_entry (
    trip_id     integer NOT NULL REFERENCES trip(id) ON DELETE CASCADE,
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    day_number  integer,
    day_label   text,
    is_travel_day boolean DEFAULT false,
    is_rest_day   boolean DEFAULT false,
    PRIMARY KEY (trip_id, entry_id)
);

CREATE TABLE IF NOT EXISTS trip_highlight (
    id              serial PRIMARY KEY,
    trip_id         integer NOT NULL REFERENCES trip(id) ON DELETE CASCADE,
    entry_id        integer REFERENCES entry(id) ON DELETE SET NULL,
    title           text NOT NULL,
    description     text,
    sequence_order  integer NOT NULL DEFAULT 0,
    asset_id        text                -- immich asset for the highlight
);

CREATE INDEX IF NOT EXISTS idx_trip_highlight_trip ON trip_highlight (trip_id);

CREATE TABLE IF NOT EXISTS trip_stat (
    id       serial PRIMARY KEY,
    trip_id  integer NOT NULL REFERENCES trip(id) ON DELETE CASCADE,
    key      text NOT NULL,
    value    text NOT NULL,
    unit     text,
    UNIQUE (trip_id, key)
);

-- 1f. Entry enhancements
ALTER TABLE entry ADD COLUMN IF NOT EXISTS entry_type text NOT NULL DEFAULT 'diary';  -- 'diary' | 'retrospective'
ALTER TABLE entry ADD COLUMN IF NOT EXISTS mood integer;      -- 1-5
ALTER TABLE entry ADD COLUMN IF NOT EXISTS energy integer;    -- 1-5

-- 1g. Multi-location support
ALTER TABLE location ADD COLUMN IF NOT EXISTS location_type text NOT NULL DEFAULT 'primary';
ALTER TABLE location ADD COLUMN IF NOT EXISTS sequence_order integer DEFAULT 0;

-- Drop UNIQUE on location.entry_id to allow multiple locations per entry
DO $$
BEGIN
    ALTER TABLE location DROP CONSTRAINT IF EXISTS location_entry_id_key;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

-- Ensure only one primary location per entry
CREATE UNIQUE INDEX IF NOT EXISTS idx_location_primary_unique
    ON location (entry_id) WHERE location_type = 'primary';

-- 1h. person + entry_person
CREATE TABLE IF NOT EXISTS person (
    id              serial PRIMARY KEY,
    name            text NOT NULL,
    nickname        text,
    immich_person_id text,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_person_name ON person (name);

CREATE TABLE IF NOT EXISTS entry_person (
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    person_id   integer NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    role        text,                   -- e.g. 'companion', 'host', 'met'
    PRIMARY KEY (entry_id, person_id)
);


-- ============================================================
-- Phase 2: Daily Summary — parent/child entry hierarchy
-- ============================================================

-- 2a. parent_entry_id — self-referencing FK for daily_summary → child entries
ALTER TABLE entry ADD COLUMN IF NOT EXISTS parent_entry_id integer REFERENCES entry(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_entry_parent ON entry (parent_entry_id) WHERE parent_entry_id IS NOT NULL;

-- 2b. Enforce one daily_summary per calendar day
CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_daily_summary_unique
    ON entry (gregorian_year, gregorian_month, gregorian_day)
    WHERE entry_type = 'daily_summary';

-- 2c. View: canonical entry for each day (explicit summary or implicit single-entry)
CREATE OR REPLACE VIEW daily_summary_v AS
  SELECT id AS summary_entry_id, gregorian_year, gregorian_month, gregorian_day,
         'explicit' AS summary_kind
  FROM entry WHERE entry_type = 'daily_summary'
  UNION ALL
  SELECT id AS summary_entry_id, gregorian_year, gregorian_month, gregorian_day,
         'implicit' AS summary_kind
  FROM entry
  WHERE entry_type = 'diary'
    AND parent_entry_id IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM entry ds
      WHERE ds.entry_type = 'daily_summary'
        AND ds.gregorian_year = entry.gregorian_year
        AND ds.gregorian_month = entry.gregorian_month
        AND ds.gregorian_day = entry.gregorian_day
    );

-- ============================================================
-- Events
-- ============================================================

CREATE TABLE IF NOT EXISTS event_type (
    id   serial PRIMARY KEY,
    name text   NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS event (
    id               serial PRIMARY KEY,
    title            text NOT NULL,
    event_date       date NOT NULL,
    end_date         date,
    event_type_id    integer NOT NULL REFERENCES event_type(id),
    notes            text,
    fuzzy_date       boolean NOT NULL DEFAULT false,
    latitude         double precision,
    longitude        double precision,
    place_id         integer,
    place_label      text,
    trip_id          integer REFERENCES trip(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    modified_at      timestamptz NOT NULL DEFAULT now(),
    -- External sync (Apple Calendar etc.) — NULL for manual events.
    external_id      text,
    source           text,
    calendar_account text,
    calendar_name    text,
    start_time       timestamptz,
    end_time         timestamptz,
    all_day          boolean NOT NULL DEFAULT false,
    deleted_at       timestamptz
);
CREATE INDEX IF NOT EXISTS idx_event_date ON event (event_date);
CREATE INDEX IF NOT EXISTS idx_event_type_id ON event (event_type_id);
CREATE INDEX IF NOT EXISTS idx_event_trip ON event (trip_id) WHERE trip_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_event_external_day
    ON event (external_id, event_date) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_source
    ON event (source) WHERE source IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_deleted_at
    ON event (deleted_at) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS calendar_ignore_rule (
    id          serial PRIMARY KEY,
    kind        text NOT NULL CHECK (kind IN ('substring','exact','regex')),
    value       text NOT NULL,
    active      boolean NOT NULL DEFAULT true,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS calendar_source (
    id          serial PRIMARY KEY,
    account     text NOT NULL,
    calendar    text NOT NULL,
    active      boolean NOT NULL DEFAULT true,
    UNIQUE (account, calendar)
);

CREATE TABLE IF NOT EXISTS event_document (
    event_id        integer NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    paperless_id    integer NOT NULL,
    label           text,
    PRIMARY KEY (event_id, paperless_id)
);

CREATE TABLE IF NOT EXISTS entry_event (
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    event_id    integer NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_entry_event_event ON entry_event (event_id);


-- ============================================================
-- Memoirs — narrative sections covering periods of life
-- ============================================================

CREATE TABLE IF NOT EXISTS memoir (
    id              serial PRIMARY KEY,
    parent_id       integer REFERENCES memoir(id) ON DELETE CASCADE,
    title           text NOT NULL,
    start_year      integer,
    start_month     integer,
    end_year        integer,
    end_month       integer,
    date_label      text,
    description     text,
    entry_id        integer REFERENCES entry(id) ON DELETE SET NULL,
    cover_asset_id  text,
    sort_order      integer DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    modified_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memoir_parent ON memoir (parent_id);
CREATE INDEX IF NOT EXISTS idx_memoir_years ON memoir (start_year, end_year);

CREATE TABLE IF NOT EXISTS memoir_entry (
    memoir_id   integer NOT NULL REFERENCES memoir(id) ON DELETE CASCADE,
    entry_id    integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    PRIMARY KEY (memoir_id, entry_id)
);

-- ============================================================
-- Flights (migrated from mylocation)
-- ============================================================

CREATE TABLE IF NOT EXISTS flight (
    id                   serial PRIMARY KEY,
    date                 date NOT NULL,
    flight_number        text,
    dep_airport          text NOT NULL,
    dep_airport_name     text,
    dep_icao             text,
    arr_airport          text NOT NULL,
    arr_airport_name     text,
    arr_icao             text,
    dep_time             time,
    arr_time             time,
    duration             interval,
    airline              text,
    airline_code         text,
    aircraft_type        text,
    aircraft_code        text,
    registration         text,
    seat_number          text,
    seat_type            integer,
    flight_class         integer,
    flight_reason        integer,
    notes                text,
    source               text,
    gps_matched          boolean DEFAULT false,
    dep_lat              double precision,
    dep_lon              double precision,
    arr_lat              double precision,
    arr_lon              double precision,
    distance_km          integer,
    gate_origin          text,
    gate_destination     text,
    terminal_origin      text,
    terminal_destination text,
    baggage_claim        text,
    departure_delay      integer,
    arrival_delay        integer,
    route_distance       integer,
    runway_origin        text,
    runway_destination   text,
    codeshares           text,
    is_route             boolean DEFAULT false,
    times_flown          integer
);
CREATE INDEX IF NOT EXISTS idx_flight_date ON flight (date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_flight_dedup ON flight (date, dep_airport, arr_airport, COALESCE(flight_number, ''));

CREATE TABLE IF NOT EXISTS ga_flight (
    id                  serial PRIMARY KEY,
    date                date NOT NULL,
    aircraft_type       text,
    registration        text,
    captain             text,
    operating_capacity  text,
    dep_airport         text,
    arr_airport         text,
    dep_time            time,
    arr_time            time,
    hours_sep_pic       numeric,
    hours_sep_dual      numeric,
    hours_mep_pic       numeric,
    hours_mep_dual      numeric,
    hours_pic_3         numeric,
    hours_dual_3        numeric,
    hours_pic_4         numeric,
    hours_dual_4        numeric,
    hours_instrument    numeric,
    hours_total         numeric,
    instructor          text,
    exercise            text,
    comments            text,
    hours_as_instructor numeric,
    hours_simulator     numeric
);
CREATE INDEX IF NOT EXISTS idx_ga_flight_date ON ga_flight (date);

CREATE TABLE IF NOT EXISTS rail_journey (
    id            serial PRIMARY KEY,
    date          date NOT NULL,
    time          time,
    from_station  text NOT NULL,
    from_code     text,
    to_station    text NOT NULL,
    to_code       text,
    operator      text,
    ticket_type   text,
    direction     text,
    reference     text,
    train         text,
    via           text,
    price         numeric,
    currency      text,
    from_lat      double precision,
    from_lon      double precision,
    to_lat        double precision,
    to_lon        double precision,
    source        text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rail_journey_date ON rail_journey (date);

CREATE TABLE IF NOT EXISTS entry_rail_journey (
    entry_id          integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    rail_journey_id   integer NOT NULL REFERENCES rail_journey(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, rail_journey_id)
);

CREATE TABLE IF NOT EXISTS skiing_day (
    id              serial PRIMARY KEY,
    date            date NOT NULL,
    location        text,
    duration_hours  numeric,
    distance_km     numeric,
    vertical_up_m   integer,
    vertical_down_m integer,
    max_speed_kmh   numeric,
    avg_speed_kmh   numeric,
    max_altitude_m  integer,
    min_altitude_m  integer,
    num_runs        integer,
    num_lifts       integer,
    platform        text,
    season          text,
    track_id        text
);
CREATE INDEX IF NOT EXISTS idx_skiing_day_date ON skiing_day (date);

-- ---------------------------------------------------------------------------
-- Activity types — lookup table for activity categories
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_type (
    id serial PRIMARY KEY,
    name text NOT NULL UNIQUE
);
INSERT INTO activity_type (name) VALUES
    ('walking'), ('running'), ('cycling'), ('swimming'), ('hiking'), ('skiing')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Activity table extensions — support standalone activities + Strava sync
-- ---------------------------------------------------------------------------

-- Make entry_id nullable (Strava activities exist before journal linking)
DO $$ BEGIN
    ALTER TABLE activity ALTER COLUMN entry_id DROP NOT NULL;
EXCEPTION WHEN others THEN NULL;
END $$;

-- Add activity_type_id FK (structured replacement for free-text activity_type)
ALTER TABLE activity ADD COLUMN IF NOT EXISTS activity_type_id integer REFERENCES activity_type(id);

-- Add Strava cross-reference
ALTER TABLE activity ADD COLUMN IF NOT EXISTS strava_activity_id bigint UNIQUE;

-- Add useful non-GPS fields from Strava
ALTER TABLE activity ADD COLUMN IF NOT EXISTS date date;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS start_time time;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS moving_time_seconds integer;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS avg_speed_kmh float;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS max_speed_kmh float;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS avg_heartrate float;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS max_heartrate float;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS calories float;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual';  -- 'manual' | 'strava'

CREATE INDEX IF NOT EXISTS idx_activity_date ON activity (date);
CREATE INDEX IF NOT EXISTS idx_activity_strava_id ON activity (strava_activity_id) WHERE strava_activity_id IS NOT NULL;

-- Apple Health import support
ALTER TABLE activity ADD COLUMN IF NOT EXISTS apple_health_id text UNIQUE;
ALTER TABLE activity ADD COLUMN IF NOT EXISTS steps integer;
CREATE INDEX IF NOT EXISTS idx_activity_apple_health_id
    ON activity (apple_health_id) WHERE apple_health_id IS NOT NULL;

-- Backfill activity_type_id from free-text activity_type column
UPDATE activity a SET activity_type_id = at.id
FROM activity_type at WHERE lower(a.activity_type) = at.name
AND a.activity_type_id IS NULL;

-- Aircraft narrative cache (Claude-generated)
CREATE TABLE IF NOT EXISTS aircraft_narrative (
    registration    text PRIMARY KEY,
    narrative       text NOT NULL,
    model           text NOT NULL,
    generated_at    timestamptz NOT NULL DEFAULT now(),
    register_data   jsonb
);

-- Archived narrative versions (kept on 12-month refresh)
CREATE TABLE IF NOT EXISTS aircraft_narrative_history (
    id              serial PRIMARY KEY,
    registration    text NOT NULL,
    narrative       text NOT NULL,
    model           text NOT NULL,
    register_data   jsonb,
    generated_at    timestamptz NOT NULL,
    archived_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aircraft_narrative_history_reg
    ON aircraft_narrative_history (registration);
