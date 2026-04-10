#!/usr/bin/env python3
"""Re-geocode location place_name using structured address fields.

Fixes entries where place_name was set from display_name split (street-level)
instead of from structured address fields (suburb/neighbourhood).

Processes all locations with coordinates, respecting Nominatim 1req/s rate limit.

Exit codes:
  0 = success
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

HC_BASE = "https://hc.mees.st/ping"


def ping_healthcheck(uuid: str, suffix: str = ""):
    if not uuid:
        return
    try:
        httpx.get(f"{HC_BASE}/{uuid}{suffix}", timeout=5)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Re-geocode place_name for existing locations")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=0, help="Batch size (0 = all)")
    parser.add_argument("--healthcheck-uuid", type=str, default="", help="Healthchecks.io UUID")
    args = parser.parse_args()

    hc_uuid = args.healthcheck_uuid
    ping_healthcheck(hc_uuid, "/start")

    conn = psycopg2.connect(settings.dsn)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # All locations with coordinates — re-geocode everything
    cur.execute("""
        SELECT id, latitude, longitude, place_name, locality
        FROM location
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY id
    """)
    all_rows = cur.fetchall()
    rows = all_rows[:args.batch] if args.batch > 0 else all_rows

    print(f"Total locations with coordinates: {len(all_rows)}")
    print(f"Processing: {len(rows)}")

    stats = {"updated": 0, "unchanged": 0, "errors": 0}

    for i, row in enumerate(rows):
        try:
            geo = reverse_geocode(float(row["latitude"]), float(row["longitude"]))
            time.sleep(1)  # Nominatim rate limit

            new_place = geo.get("place_name")
            old_place = row["place_name"]

            if new_place and new_place != old_place:
                if args.dry_run:
                    print(f"  [DRY RUN] id={row['id']}: '{old_place}' -> '{new_place}'")
                else:
                    cur.execute(
                        """UPDATE location
                           SET place_name = %s, locality = %s,
                               admin_area = %s, country = %s
                           WHERE id = %s""",
                        (new_place, geo.get("locality"),
                         geo.get("admin_area"), geo.get("country"),
                         row["id"]),
                    )
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1

            if not args.dry_run and (i + 1) % 50 == 0:
                conn.commit()
                print(f"  Progress: {i+1}/{len(rows)}, updated={stats['updated']}, unchanged={stats['unchanged']}")

        except Exception as e:
            print(f"  ERROR on id={row['id']}: {e}")
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

    if stats["errors"] > 0:
        ping_healthcheck(hc_uuid, "/fail")
        sys.exit(1)
    else:
        ping_healthcheck(hc_uuid)


if __name__ == "__main__":
    main()
