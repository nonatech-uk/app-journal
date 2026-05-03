-- Apple Calendar → journal sync.
--
-- Adds external-source columns to event, an "appointment" event_type, and two
-- supporting tables (calendar_source allow-list, calendar_ignore_rule). All
-- additive — existing 63 manually-curated events keep their NULL external_id
-- and are excluded from the upsert unique index.

BEGIN;

INSERT INTO event_type (name) VALUES ('appointment') ON CONFLICT (name) DO NOTHING;

ALTER TABLE event
    ADD COLUMN IF NOT EXISTS external_id      text,
    ADD COLUMN IF NOT EXISTS source           text,
    ADD COLUMN IF NOT EXISTS calendar_account text,
    ADD COLUMN IF NOT EXISTS calendar_name    text,
    ADD COLUMN IF NOT EXISTS start_time       timestamptz,
    ADD COLUMN IF NOT EXISTS end_time         timestamptz,
    ADD COLUMN IF NOT EXISTS all_day          boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS deleted_at       timestamptz;

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

INSERT INTO calendar_source (account, calendar)
VALUES ('Mees', 'Fun Stuff')
ON CONFLICT (account, calendar) DO NOTHING;

COMMIT;
