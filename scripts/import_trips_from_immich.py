#!/usr/bin/env python3
"""Import trips from Immich albums CSV into the trip table.

Reads the user-reviewed CSV (with include/exclude column), creates trip records
for included albums, and links journal entries that fall within the trip date range.

Usage:
    python scripts/import_trips_from_immich.py [--dry-run] [--csv PATH]
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import psycopg2.extras

from config.settings import settings

DEFAULT_CSV = "/zfs/tank/home/stu/immich_trip_albums.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import trips from Immich albums CSV")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without updating DB")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV, help=f"Path to CSV (default: {DEFAULT_CSV})")
    return parser.parse_args()


def parse_date(s: str) -> str | None:
    """Parse date in DD/MM/YYYY or YYYY-MM-DD format, return YYYY-MM-DD."""
    s = s.strip()
    if not s:
        return None
    result = None
    # DD/MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        result = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    # YYYY-MM-DD (already correct)
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        result = s
    # Validate the date is real
    if result:
        try:
            datetime.strptime(result, "%Y-%m-%d")
        except ValueError:
            print(f"  WARN: invalid date '{s}' -> '{result}', skipping")
            return None
    return result


def parse_locations(s: str) -> list[str]:
    """Parse semicolon-separated locations into a list of unique values."""
    if not s or not s.strip():
        return []
    locs = [l.strip() for l in s.split(";") if l.strip()]
    # Deduplicate preserving order
    seen = set()
    result = []
    for loc in locs:
        if loc not in seen:
            seen.add(loc)
            result.append(loc)
    return result


def extract_countries(locations: list[str]) -> list[str]:
    """Extract unique country names from 'City, Country' location strings."""
    countries = []
    seen = set()
    for loc in locations:
        parts = loc.rsplit(", ", 1)
        if len(parts) == 2:
            country = parts[1]
            if country not in seen:
                seen.add(country)
                countries.append(country)
    return countries


def slugify(title: str) -> str:
    """Create a simple ltree label from a title."""
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "trip"


def main() -> None:
    args = parse_args()

    print(f"CSV: {args.csv}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Read CSV
    with open(args.csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    included = [r for r in rows if r["include"].strip().lower() == "include"]
    print(f"Total rows: {len(rows)}, included: {len(included)}")
    print()

    conn = psycopg2.connect(settings.dsn)
    conn.autocommit = False

    stats = {"created": 0, "skipped_exists": 0, "entries_linked": 0, "skipped_no_date": 0}

    try:
        cur = conn.cursor()

        for row in included:
            start_date = parse_date(row["date"])
            end_date = parse_date(row.get("end_date", ""))
            title = row["title"].strip()
            album_id = row["album_id"].strip()
            locations = parse_locations(row.get("locations", ""))
            countries = extract_countries(locations)
            assets = int(row.get("assets", 0) or 0)

            if not start_date:
                print(f"  SKIP (no date): {title}")
                stats["skipped_no_date"] += 1
                continue

            # Use start_date as end_date if not available
            if not end_date:
                end_date = start_date

            # Check if trip already exists for this album
            cur.execute("SELECT id FROM trip WHERE immich_album_id = %s", (album_id,))
            if cur.fetchone():
                stats["skipped_exists"] += 1
                continue

            # Build ltree path: year.slug
            year = start_date[:4]
            slug = slugify(title)
            path = f"{year}.{slug}"

            if args.dry_run:
                print(f"  [DRY RUN] CREATE trip: {title} ({start_date} -> {end_date}) path={path} countries={countries}")
            else:
                cur.execute(
                    """INSERT INTO trip (path, title, start_date, end_date, countries, locations, immich_album_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (path, title, start_date, end_date, countries, locations, album_id),
                )
                trip_id = cur.fetchone()[0]
                stats["created"] += 1

                # Link journal entries within the trip date range
                cur.execute(
                    """INSERT INTO trip_entry (trip_id, entry_id, day_number)
                       SELECT %s, e.id, (e.created_at::date - %s::date) + 1
                       FROM entry e
                       WHERE e.created_at::date >= %s AND e.created_at::date <= %s
                       ON CONFLICT DO NOTHING""",
                    (trip_id, start_date, start_date, end_date),
                )
                linked = cur.rowcount
                stats["entries_linked"] += linked

                if linked > 0:
                    print(f"  Created trip: {title} ({start_date} -> {end_date}) — {linked} entries linked")

        if not args.dry_run:
            conn.commit()
            print("\nCommitted.")
        else:
            conn.rollback()

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()

    print()
    print("=== Summary ===")
    print(f"  Trips created:       {stats['created']}")
    print(f"  Already existed:     {stats['skipped_exists']}")
    print(f"  Skipped (no date):   {stats['skipped_no_date']}")
    print(f"  Entries linked:      {stats['entries_linked']}")


if __name__ == "__main__":
    main()
