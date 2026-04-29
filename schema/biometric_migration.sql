-- biometric_sample: raw timeseries for HealthKit-style metrics streamed from
-- HA Companion (and later, Apple Health export). One row per state change.
-- Cumulative iOS counters (steps, distance, floors) reset at local midnight,
-- so we store both the raw cumulative reading and the delta from the previous
-- sample, computed at insert time.

BEGIN;

CREATE TABLE IF NOT EXISTS biometric_sample (
    id                   bigserial PRIMARY KEY,
    ts                   timestamptz NOT NULL,
    device_id            text NOT NULL,
    metric               text NOT NULL,
    value_numeric        double precision,
    value_unit           text,
    delta_from_previous  double precision,
    source               text NOT NULL,
    raw_state            jsonb,
    UNIQUE (device_id, metric, ts)
);

CREATE INDEX IF NOT EXISTS idx_biometric_device_metric_ts
    ON biometric_sample (device_id, metric, ts DESC);

CREATE INDEX IF NOT EXISTS idx_biometric_metric_ts
    ON biometric_sample (metric, ts DESC);

COMMIT;
