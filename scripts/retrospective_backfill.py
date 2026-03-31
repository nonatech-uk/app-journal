#!/usr/bin/env python3
"""Retrospective backfill — create journal entries for dates with activity data but no entry.

Usage:
    python scripts/retrospective_backfill.py [--dry-run] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings
from src.services.retrospective import (
    collect_day_data,
    create_retrospective_entry,
    discover_candidate_dates,
    filter_missing_dates,
    generate_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create retrospective entries for dates with activity data")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be created without writing")
    parser.add_argument("--start-date", type=str, default=None, help="Earliest date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="Latest date (YYYY-MM-DD)")
    parser.add_argument("--last-n-days", type=int, default=None, help="Process last N days only")
    parser.add_argument("--max-photos-per-day", type=int, default=6, help="Photos to link per entry (default: 6)")
    parser.add_argument("--skip-photos", action="store_true", help="Skip photo download")
    parser.add_argument("--skip-weather", action="store_true", help="Skip historical weather lookup")
    parser.add_argument("--immich-url", type=str, default=None, help="Override Immich URL")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.immich_url:
        settings.immich_url = args.immich_url

    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    if args.last_n_days:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.last_n_days)

    print(f"Immich URL: {settings.immich_url}")
    print(f"Date range: {start_date or 'all'} to {end_date or 'today'}")
    print(f"Dry run: {args.dry_run}")
    print(f"Max photos/day: {args.max_photos_per_day}")
    print(f"Skip photos: {args.skip_photos}")
    print(f"Skip weather: {args.skip_weather}")
    print()

    conn = psycopg2.connect(settings.dsn)
    conn.autocommit = False
    client = httpx.Client(timeout=30)

    stats = {
        "entries_created": 0, "photos_attached": 0, "flights_linked": 0,
        "ga_flights_linked": 0, "skiing_linked": 0, "scrobbles_linked": 0,
        "watches_linked": 0, "locations_added": 0, "weather_added": 0,
        "errors": 0, "skipped_empty": 0,
    }

    try:
        # Phase 1: Discovery
        print("=== Phase 1: Discovering candidate dates ===")
        sources = discover_candidate_dates(settings, client, start_date, end_date)
        all_candidates: set[date] = set()
        for name, dates in sources.items():
            print(f"  {name}: {len(dates)} dates")
            all_candidates |= dates
        print(f"  UNION: {len(all_candidates)} unique dates")
        print()

        # Phase 2: Filter
        print("=== Phase 2: Filtering to missing dates ===")
        missing = filter_missing_dates(conn, all_candidates)
        print(f"  {len(all_candidates)} candidates, {len(all_candidates) - len(missing)} already have entries, processing {len(missing)}")
        print()

        if not missing:
            print("Nothing to do!")
            return

        # Phase 3: Process
        print(f"=== Phase 3: Processing {len(missing)} dates ===")
        for i, d in enumerate(missing):
            try:
                day_data = collect_day_data(settings, client, d)

                # Skip if no meaningful data at all
                has_data = (day_data.flights or day_data.ga_flights or day_data.skiing
                           or day_data.scrobbles or day_data.watches or day_data.photos)
                if not has_data:
                    stats["skipped_empty"] += 1
                    continue

                markdown = generate_markdown(day_data)

                if args.dry_run:
                    sources_str = []
                    if day_data.flights: sources_str.append(f"{len(day_data.flights)} flights")
                    if day_data.ga_flights: sources_str.append(f"{len(day_data.ga_flights)} GA flights")
                    if day_data.skiing: sources_str.append(f"{len(day_data.skiing)} skiing")
                    if day_data.scrobbles: sources_str.append(f"{len(day_data.scrobbles)} scrobbles")
                    if day_data.watches: sources_str.append(f"{len(day_data.watches)} watches")
                    if day_data.photos: sources_str.append(f"{len(day_data.photos)} photos")
                    loc_str = ""
                    if day_data.location:
                        loc_str = f" @ {day_data.location.get('place_name') or day_data.location.get('country') or '?'}"
                    print(f"  [DRY RUN] {d}: {', '.join(sources_str)}{loc_str}")
                else:
                    entry_id = create_retrospective_entry(
                        conn, settings, client, day_data, markdown,
                        max_photos=args.max_photos_per_day,
                        skip_photos=args.skip_photos,
                        skip_weather=args.skip_weather,
                    )
                    if entry_id:
                        stats["entries_created"] += 1
                        stats["flights_linked"] += len(day_data.flights)
                        stats["ga_flights_linked"] += len(day_data.ga_flights)
                        stats["skiing_linked"] += len(day_data.skiing)
                        stats["scrobbles_linked"] += len(day_data.scrobbles)
                        stats["watches_linked"] += len(day_data.watches)
                        if day_data.location:
                            stats["locations_added"] += 1
                        if not args.skip_photos:
                            stats["photos_attached"] += min(len(day_data.photos), args.max_photos_per_day)

            except Exception as e:
                print(f"  ERROR on {d}: {e}")
                stats["errors"] += 1
                try:
                    conn.rollback()
                except Exception:
                    pass

            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(missing)} dates processed, {stats['entries_created']} entries created")

    except KeyboardInterrupt:
        print("\nInterrupted.")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        client.close()
        conn.close()

    # Summary
    print()
    print("=== Summary ===")
    for k, v in stats.items():
        print(f"  {k:25s} {v}")


if __name__ == "__main__":
    main()
