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
    search_vector   tsvector
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
    user_label      text
);

CREATE INDEX IF NOT EXISTS idx_location_coords ON location (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_location_entry_id ON location (entry_id);


CREATE TABLE IF NOT EXISTS weather (
    id                  serial PRIMARY KEY,
    entry_id            integer NOT NULL REFERENCES entry(id) ON DELETE CASCADE UNIQUE,
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
    sunset              timestamptz
);

CREATE INDEX IF NOT EXISTS idx_weather_entry_id ON weather (entry_id);


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
