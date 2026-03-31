#!/usr/bin/env python3
"""Backfill weather and location for retrospective entries using gps_points.

Targets retrospective entries that have no weather record.
Designed to run as a daily Cronicle job with healthcheck integration.

Exit codes:
  0 = success (processed some entries, or nothing left to do)
  1 = error
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2
import psycopg2.extras

from config.settings import settings
from src.services.location import reverse_geocode
from src.services.retrospective import _safe_query
from src.services.weather import get_historical_weather

HC_BASE = "https://hc.mees.st/ping"


def ping_healthcheck(uuid: str, suffix: str = ""):
    """Ping healthcheck. suffix: '' for success, '/start' for start, '/fail' for failure."""
    if not uuid:
        return
    try:
        httpx.get(f"{HC_BASE}/{uuid}{suffix}", timeout=5)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Backfill weather/location for retrospective entries")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=100, help="Max entries to process (default: 100)")
    parser.add_argument("--healthcheck-uuid", type=str, default="", help="Healthchecks.io UUID")
    args = parser.parse_args()

    hc_uuid = args.healthcheck_uuid

    ping_healthcheck(hc_uuid, "/start")

    conn = psycopg2.connect(settings.dsn)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Find canonical entries (daily_summary or solo retrospective) without weather.
    # Skip children — their weather lives on the summary.
    cur.execute("""
        SELECT e.id, e.created_at::date AS d
        FROM entry e
        LEFT JOIN weather w ON w.entry_id = e.id
        WHERE e.entry_type IN ('retrospective', 'daily_summary')
          AND e.parent_entry_id IS NULL
          AND w.id IS NULL
        ORDER BY e.created_at
    """)
    all_rows = cur.fetchall()
    total_remaining = len(all_rows)
    rows = all_rows[:args.limit]

    print(f"Remaining without weather: {total_remaining}")
    if total_remaining == 0:
        print("All done!")
        ping_healthcheck(hc_uuid)
        conn.close()
        return

    print(f"Processing batch of {len(rows)}")

    mylocation_dsn = settings.cross_dsn(settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password)

    stats = {"location_added": 0, "weather_added": 0, "no_gps": 0, "errors": 0}

    for i, row in enumerate(rows):
        entry_id = row["id"]
        d = row["d"]

        try:
            # Get GPS for this date
            gps = _safe_query(mylocation_dsn,
                """SELECT avg(lat) AS lat, avg(lon) AS lon
                   FROM gps_points WHERE ts::date = %s AND lat IS NOT NULL""",
                (d,))

            if not gps or not gps[0].get("lat"):
                stats["no_gps"] += 1
                continue

            lat = float(gps[0]["lat"])
            lon = float(gps[0]["lon"])

            if args.dry_run:
                print(f"  [DRY RUN] {d}: lat={lat:.4f} lon={lon:.4f}")
                stats["weather_added"] += 1
                continue

            # Check if location exists
            cur.execute("SELECT id FROM location WHERE entry_id = %s", (entry_id,))
            if not cur.fetchone():
                geo = reverse_geocode(lat, lon)
                time.sleep(1)
                cur.execute(
                    """INSERT INTO location (entry_id, latitude, longitude, place_name,
                                             locality, admin_area, country, location_type)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'primary')""",
                    (entry_id, lat, lon, geo.get("place_name"), geo.get("locality"),
                     geo.get("admin_area"), geo.get("country")),
                )
                stats["location_added"] += 1

            # Add weather
            weather = get_historical_weather(lat, lon, d.isoformat())
            time.sleep(0.5)
            if weather:
                cur.execute(
                    """INSERT INTO weather (entry_id, temp_celsius, conditions,
                                            weather_code, wind_speed_kph)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (entry_id, weather.get("temp_celsius"), weather.get("conditions"),
                     weather.get("weather_code"), weather.get("wind_speed_kph")),
                )
                stats["weather_added"] += 1

            if (i + 1) % 50 == 0:
                conn.commit()
                print(f"  Progress: {i+1}/{len(rows)}, weather={stats['weather_added']}, loc={stats['location_added']}")

        except Exception as e:
            print(f"  ERROR on {d}: {e}")
            stats["errors"] += 1
            try:
                conn.rollback()
            except Exception:
                pass

    if not args.dry_run:
        conn.commit()

    conn.close()

    print()
    print("=== Summary ===")
    for k, v in stats.items():
        print(f"  {k:20s} {v}")
    print(f"  {'remaining':20s} {total_remaining - len(rows)}")

    # Healthcheck: fail if errors, otherwise success
    if stats["errors"] > 0:
        ping_healthcheck(hc_uuid, "/fail")
        sys.exit(1)
    else:
        ping_healthcheck(hc_uuid)


if __name__ == "__main__":
    main()
