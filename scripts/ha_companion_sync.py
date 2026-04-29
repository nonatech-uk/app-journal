#!/usr/bin/env python3
"""HA Companion sync — pull iOS Home Assistant Companion data into archives.

Targets:
- mylocation.gps_points (lat/lon/altitude/wifi/motion as source_type='ha-companion')
- journal.biometric_sample (HealthKit raw timeseries)
- journal.activity (daily rollup, source='ha-companion')

Usage:
    python scripts/ha_companion_sync.py                       # last 1h, default Cronicle invocation
    python scripts/ha_companion_sync.py --since 2026-04-22    # backfill from date (UTC)
    python scripts/ha_companion_sync.py --window-hours 2      # extend the lookback window

Run from inside the journal container:
    podman exec journal python /app/scripts/ha_companion_sync.py
"""

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2
from psycopg2.extras import Json, execute_values

from config.settings import settings

log = logging.getLogger("ha_companion_sync")

DEVICE_ID = "ha-companion-mees-only"
DEVICE_TRACKER = "device_tracker.mees_only"
GEOCODE_SENSOR = "sensor.mees_only_geocoded_location"
SSID_SENSOR = "sensor.mees_only_ssid"
BSSID_SENSOR = "sensor.mees_only_bssid"
CONNECTION_SENSOR = "sensor.mees_only_connection_type"
ACTIVITY_SENSOR = "sensor.mees_only_activity"

LOCATION_ENTITIES = [
    DEVICE_TRACKER,
    GEOCODE_SENSOR,
    SSID_SENSOR,
    BSSID_SENSOR,
    CONNECTION_SENSOR,
    ACTIVITY_SENSOR,
]

# HealthKit cumulative counters (reset at iOS local midnight)
BIOMETRIC_CUMULATIVE = {
    "sensor.mees_only_steps": ("steps", "steps"),
    "sensor.mees_only_distance": ("distance_m", "m"),
    "sensor.mees_only_floors_ascended": ("floors_ascended", "floors"),
    "sensor.mees_only_floors_descended": ("floors_descended", "floors"),
}
# Instantaneous metrics (no delta logic)
BIOMETRIC_INSTANT = {
    "sensor.mees_only_average_active_pace": ("active_pace_mps", "m/s"),
    "sensor.mees_only_watch_battery_level": ("watch_battery_pct", "%"),
}
BIOMETRIC_ALL = {**BIOMETRIC_CUMULATIVE, **BIOMETRIC_INSTANT}

ALL_ENTITIES = LOCATION_ENTITIES + list(BIOMETRIC_ALL.keys())

UNAVAILABLE = {"unavailable", "unknown", "none", "not connected", ""}


# ---------------------------------------------------------------------------
# HA REST helpers
# ---------------------------------------------------------------------------

def _ha_get(client: httpx.Client, path: str, **params) -> object:
    r = client.get(path, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_history(client: httpx.Client, since: datetime, until: datetime) -> dict[str, list[dict]]:
    """Return {entity_id: [state_dict, ...]} for the configured entities."""
    path = f"/api/history/period/{since.replace(microsecond=0).isoformat().replace('+00:00', '')}"
    raw = _ha_get(
        client,
        path,
        filter_entity_id=",".join(ALL_ENTITIES),
        end_time=until.replace(microsecond=0).isoformat().replace("+00:00", ""),
    )
    out: dict[str, list[dict]] = {}
    for stream in raw or []:
        if not stream:
            continue
        eid = stream[0].get("entity_id")
        if not eid:
            continue
        # `minimal_response` is NOT requested so attributes are present on every row.
        out[eid] = stream
    return out


def fetch_current(client: httpx.Client, entity_id: str) -> dict | None:
    try:
        return _ha_get(client, f"/api/states/{entity_id}")
    except httpx.HTTPError:
        return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_unavailable(state: str | None) -> bool:
    return state is None or state.strip().lower() in UNAVAILABLE


def parse_float(s) -> float | None:
    if s is None:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Build gps_points rows
# ---------------------------------------------------------------------------

GPS_INSERT_SQL = """
    INSERT INTO gps_points (
        device_id, device_name, ts, lat, lon, altitude_m, altitude_ft,
        speed_mph, speed_kmh, direction, accuracy_m, battery_pct, source_type,
        connection_type, wifi_ssid, wifi_bssid, vertical_accuracy_m,
        motion_activity, motion_confidence, raw_payload, geom
    ) VALUES %s
    ON CONFLICT (device_id, ts) DO NOTHING
"""

GPS_INSERT_TEMPLATE = """(
    %(device_id)s, %(device_name)s, %(ts)s, %(lat)s, %(lon)s,
    %(altitude_m)s, %(altitude_ft)s, %(speed_mph)s, %(speed_kmh)s,
    %(direction)s, %(accuracy_m)s, %(battery_pct)s, %(source_type)s,
    %(connection_type)s, %(wifi_ssid)s, %(wifi_bssid)s, %(vertical_accuracy_m)s,
    %(motion_activity)s, %(motion_confidence)s, %(raw_payload)s,
    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)
)"""

M_TO_FT = 3.28084
MPS_TO_KMH = 3.6
KMH_TO_MPH = 0.621371


def _attr_lookup(stream: list[dict], ts: datetime) -> dict:
    """Find the state in `stream` valid at `ts` (most recent state with last_changed <= ts)."""
    best = None
    for row in stream:
        rt = parse_ts(row.get("last_changed"))
        if rt is None or rt > ts:
            continue
        if best is None or rt > parse_ts(best.get("last_changed")):
            best = row
    return best or {}


def build_gps_rows(history: dict[str, list[dict]]) -> list[dict]:
    """Use device_tracker as the spine; enrich with wifi/connection/motion at each point."""
    spine = history.get(DEVICE_TRACKER, [])
    if not spine:
        return []

    geocode_stream = history.get(GEOCODE_SENSOR, [])
    ssid_stream = history.get(SSID_SENSOR, [])
    bssid_stream = history.get(BSSID_SENSOR, [])
    conn_stream = history.get(CONNECTION_SENSOR, [])
    activity_stream = history.get(ACTIVITY_SENSOR, [])

    rows: list[dict] = []
    for tracker in spine:
        attrs = tracker.get("attributes") or {}
        lat = parse_float(attrs.get("latitude"))
        lon = parse_float(attrs.get("longitude"))
        ts = parse_ts(tracker.get("last_changed"))
        if lat is None or lon is None or ts is None:
            continue

        alt_m = parse_float(attrs.get("altitude"))
        speed_mps = parse_float(attrs.get("speed"))
        speed_kmh = round(speed_mps * MPS_TO_KMH, 2) if speed_mps is not None else None
        speed_mph = round(speed_kmh * KMH_TO_MPH, 2) if speed_kmh is not None else None

        ssid_state = _attr_lookup(ssid_stream, ts).get("state")
        bssid_state = _attr_lookup(bssid_stream, ts).get("state")
        conn_state = _attr_lookup(conn_stream, ts).get("state")
        activity_row = _attr_lookup(activity_stream, ts)
        activity_state = activity_row.get("state")
        activity_attrs = activity_row.get("attributes") or {}
        geocode_row = _attr_lookup(geocode_stream, ts)

        raw_payload = {
            "device_tracker_state": tracker.get("state"),
            "tracker_attributes": attrs,
            "geocode": {
                "state": geocode_row.get("state"),
                "attributes": geocode_row.get("attributes"),
            } if geocode_row else None,
            "ssid_raw": ssid_state,
            "bssid_raw": bssid_state,
            "connection_raw": conn_state,
            "activity_raw": activity_state,
            "activity_attributes": activity_attrs,
        }

        rows.append({
            "device_id": DEVICE_ID,
            "device_name": "iPhone (HA Companion)",
            "ts": ts,
            "lat": lat,
            "lon": lon,
            "altitude_m": alt_m,
            "altitude_ft": round(alt_m * M_TO_FT, 1) if alt_m is not None else None,
            "speed_mph": speed_mph,
            "speed_kmh": speed_kmh,
            "direction": parse_float(attrs.get("course")),
            "accuracy_m": parse_float(attrs.get("gps_accuracy")),
            "battery_pct": parse_float(attrs.get("battery_level")),
            "source_type": "ha-companion",
            "connection_type": None if is_unavailable(conn_state) else conn_state,
            "wifi_ssid": None if is_unavailable(ssid_state) else ssid_state,
            "wifi_bssid": None if is_unavailable(bssid_state) else bssid_state,
            "vertical_accuracy_m": parse_float(attrs.get("vertical_accuracy")),
            "motion_activity": None if is_unavailable(activity_state) else activity_state,
            "motion_confidence": activity_attrs.get("Confidence"),
            "raw_payload": Json(raw_payload),
        })
    return rows


# ---------------------------------------------------------------------------
# Build biometric_sample rows
# ---------------------------------------------------------------------------

BIO_INSERT_SQL = """
    INSERT INTO biometric_sample (
        ts, device_id, metric, value_numeric, value_unit,
        delta_from_previous, source, raw_state
    ) VALUES %s
    ON CONFLICT (device_id, metric, ts) DO NOTHING
"""

BIO_INSERT_TEMPLATE = """(
    %(ts)s, %(device_id)s, %(metric)s, %(value_numeric)s, %(value_unit)s,
    %(delta_from_previous)s, %(source)s, %(raw_state)s
)"""


def build_biometric_rows(history: dict[str, list[dict]], journal_conn) -> list[dict]:
    """Stream HealthKit history into biometric_sample rows, computing deltas.

    Delta computation: for cumulative metrics, look up the most recent prior
    sample for this (device, metric) in the DB and subtract. If the new value
    is lower, treat it as a midnight reset and use the new value as the delta.
    """
    rows: list[dict] = []
    for entity_id, (metric, unit) in BIOMETRIC_ALL.items():
        stream = history.get(entity_id, [])
        if not stream:
            continue

        cumulative = entity_id in BIOMETRIC_CUMULATIVE

        # Fetch the most recent prior sample once per metric
        prev_value = None
        prev_ts = None
        if cumulative and stream:
            first_ts = parse_ts(stream[0].get("last_changed"))
            if first_ts is not None:
                cur = journal_conn.cursor()
                cur.execute(
                    "SELECT value_numeric, ts FROM biometric_sample "
                    "WHERE device_id=%s AND metric=%s AND ts < %s "
                    "ORDER BY ts DESC LIMIT 1",
                    (DEVICE_ID, metric, first_ts),
                )
                r = cur.fetchone()
                cur.close()
                if r:
                    prev_value = float(r[0]) if r[0] is not None else None
                    prev_ts = r[1]

        for state in stream:
            ts = parse_ts(state.get("last_changed"))
            raw = state.get("state")
            value = parse_float(raw)
            if ts is None or value is None or is_unavailable(raw):
                continue

            delta = None
            if cumulative:
                if prev_value is not None:
                    if value >= prev_value and (prev_ts is None or ts.date() == prev_ts.date()):
                        delta = value - prev_value
                    elif value < prev_value or (prev_ts and ts.date() != prev_ts.date()):
                        # Midnight reset: the new cumulative IS the day's delta so far.
                        delta = value
                prev_value = value
                prev_ts = ts

            rows.append({
                "ts": ts,
                "device_id": DEVICE_ID,
                "metric": metric,
                "value_numeric": value,
                "value_unit": unit,
                "delta_from_previous": delta,
                "source": "ha-companion",
                "raw_state": Json({"state": raw, "attributes": state.get("attributes")}),
            })
    return rows


# ---------------------------------------------------------------------------
# Daily activity rollup
# ---------------------------------------------------------------------------

ACTIVITY_UPSERT_SQL = """
INSERT INTO activity (
    activity_type, date, source, apple_health_id,
    steps, distance_km, notes
) VALUES (
    'daily_summary', %s, 'ha-companion', %s,
    %s, %s, %s
)
ON CONFLICT (apple_health_id) DO UPDATE SET
    steps = EXCLUDED.steps,
    distance_km = EXCLUDED.distance_km,
    notes = EXCLUDED.notes
"""


def upsert_daily_rollup(journal_conn, target_date: date) -> bool:
    """Read latest cumulative biometric_sample values for `target_date` and upsert into activity."""
    cur = journal_conn.cursor()
    cur.execute(
        """
        SELECT metric, value_numeric
        FROM (
            SELECT metric, value_numeric,
                   ROW_NUMBER() OVER (PARTITION BY metric ORDER BY ts DESC) AS rn
            FROM biometric_sample
            WHERE device_id = %s
              AND metric IN ('steps', 'distance_m', 'floors_ascended', 'floors_descended')
              AND ts >= %s
              AND ts <  %s
        ) t WHERE rn = 1
        """,
        (DEVICE_ID, target_date, target_date + timedelta(days=1)),
    )
    metrics = {row[0]: float(row[1]) for row in cur.fetchall() if row[1] is not None}
    cur.close()

    if not metrics:
        return False

    steps = int(metrics.get("steps", 0)) if "steps" in metrics else None
    distance_km = round(metrics["distance_m"] / 1000.0, 3) if "distance_m" in metrics else None
    notes_parts = []
    if "floors_ascended" in metrics:
        notes_parts.append(f"floors_ascended={int(metrics['floors_ascended'])}")
    if "floors_descended" in metrics:
        notes_parts.append(f"floors_descended={int(metrics['floors_descended'])}")
    notes = "; ".join(notes_parts) if notes_parts else None

    apple_health_id = f"ha-companion-{DEVICE_ID}-{target_date.isoformat()}"

    cur = journal_conn.cursor()
    cur.execute(ACTIVITY_UPSERT_SQL, (target_date, apple_health_id, steps, distance_km, notes))
    cur.close()
    return True


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------

def ping_hc(suffix: str = "") -> None:
    uuid = getattr(settings, "hc_ha_companion_sync", "") or ""
    if not uuid:
        return
    try:
        httpx.get(f"{settings.hc_base}/{uuid}{suffix}", timeout=5)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="HA Companion sync")
    parser.add_argument("--since", type=str, default=None, help="ISO datetime (UTC) to start from; default = now-window")
    parser.add_argument("--until", type=str, default=None, help="ISO datetime (UTC) to end at; default = now")
    parser.add_argument("--window-hours", type=float, default=1.0, help="Lookback window when --since not given")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't write")
    parser.add_argument("--no-hc", action="store_true", help="Skip healthcheck pings")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    until = datetime.fromisoformat(args.until.replace("Z", "+00:00")) if args.until else now
    if args.since:
        since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    else:
        since = until - timedelta(hours=args.window_hours)

    is_scheduled = not args.dry_run and not args.no_hc
    if is_scheduled:
        ping_hc("/start")

    ha_url = settings.ha_url.rstrip("/")
    ha_token = settings.ha_token
    if not ha_token:
        log.error("ha_token not configured")
        if is_scheduled:
            ping_hc("/fail")
        sys.exit(2)

    log.info("HA Companion sync window: %s -> %s", since.isoformat(), until.isoformat())

    journal_dsn = settings.cross_dsn(settings.db_name, settings.db_user, settings.db_password)
    mylocation_dsn = settings.cross_dsn(
        settings.mylocation_db_name,
        settings.mylocation_db_writer_user,
        settings.mylocation_db_writer_password,
    )

    had_error = False

    try:
        with httpx.Client(base_url=ha_url, headers={"Authorization": f"Bearer {ha_token}"}) as client:
            history = fetch_history(client, since, until)

        log.info("Fetched %d entity streams from HA", len(history))

        gps_rows: list[dict] = build_gps_rows(history)
        log.info("Built %d gps_points rows", len(gps_rows))

        with psycopg2.connect(journal_dsn) as journal_conn:
            bio_rows = build_biometric_rows(history, journal_conn)
            log.info("Built %d biometric_sample rows", len(bio_rows))

            if not args.dry_run and bio_rows:
                cur = journal_conn.cursor()
                execute_values(cur, BIO_INSERT_SQL, bio_rows, template=BIO_INSERT_TEMPLATE)
                cur.close()
                journal_conn.commit()

            if not args.dry_run and gps_rows:
                with psycopg2.connect(mylocation_dsn) as mloc_conn:
                    cur = mloc_conn.cursor()
                    execute_values(cur, GPS_INSERT_SQL, gps_rows, template=GPS_INSERT_TEMPLATE)
                    cur.close()
                    mloc_conn.commit()

            # Daily rollup: for every day touched by the window
            if not args.dry_run:
                touched_days = sorted({r["ts"].date() for r in bio_rows} | {until.date()})
                rolled = 0
                for d in touched_days:
                    if upsert_daily_rollup(journal_conn, d):
                        rolled += 1
                journal_conn.commit()
                log.info("Daily activity rollup: %d days upserted", rolled)

    except Exception as e:
        log.exception("HA Companion sync failed: %s", e)
        had_error = True

    if is_scheduled:
        ping_hc("/fail" if had_error else "")

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
