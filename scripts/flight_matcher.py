#!/usr/bin/env python3
"""
Match flight diary entries with GPS-detected flights.

Cross-references flightdiary entries with GPS-detected flights and merges
matching records into unified entries with source='merged'.

Usage:
    python scripts/flight_matcher.py --dry-run
    python scripts/flight_matcher.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from config.settings import settings


def get_flights_by_source(cur, source):
    """Get all flights with a specific source."""
    cur.execute("""
        SELECT id, date, flight_number, dep_airport, arr_airport,
               dep_time, arr_time, duration, airline, airline_code,
               aircraft_type, aircraft_code, registration, seat_number,
               seat_type, flight_class, flight_reason, notes,
               dep_lat, dep_lon, arr_lat, arr_lon, distance_km
        FROM flight
        WHERE source = %s
        ORDER BY date
    """, (source,))
    return cur.fetchall()


def find_matching_gps_flight(diary_flight, gps_flights):
    """
    Find a GPS-detected flight that matches a diary entry.

    Matching criteria:
    - Same departure airport (IATA code)
    - Same arrival airport (IATA code)
    - Within +/- 1 day of diary date
    """
    diary_date = diary_flight[1]
    dep_airport = diary_flight[3]
    arr_airport = diary_flight[4]

    for gps_flight in gps_flights:
        gps_date = gps_flight[1]
        gps_dep = gps_flight[3]
        gps_arr = gps_flight[4]

        if gps_dep != dep_airport or gps_arr != arr_airport:
            continue

        date_diff = abs((diary_date - gps_date).days)
        if date_diff <= 1:
            return gps_flight

    return None


def merge_flights(diary_flight, gps_flight, cur):
    """
    Merge a diary flight with a GPS flight.

    Strategy: keep diary details, mark as merged + gps_matched, delete GPS record.
    """
    diary_id = diary_flight[0]
    gps_id = gps_flight[0]

    cur.execute("""
        UPDATE flight
        SET source = 'merged', gps_matched = TRUE
        WHERE id = %s
    """, (diary_id,))

    cur.execute("DELETE FROM flight WHERE id = %s", (gps_id,))

    return diary_id


def run_matching(dry_run=False):
    """Run the flight matching process."""
    conn = psycopg2.connect(settings.dsn)
    cur = conn.cursor()

    diary_flights = get_flights_by_source(cur, 'flightdiary')
    gps_flights = get_flights_by_source(cur, 'gps-detected')

    print(f"Flight diary entries: {len(diary_flights)}")
    print(f"GPS-detected flights: {len(gps_flights)}")

    if not diary_flights or not gps_flights:
        print("No flights to match")
        cur.close()
        conn.close()
        return

    matched = []
    unmatched_diary = []
    gps_matched_ids = set()

    for diary_flight in diary_flights:
        gps_match = find_matching_gps_flight(diary_flight, gps_flights)

        if gps_match:
            matched.append((diary_flight, gps_match))
            gps_matched_ids.add(gps_match[0])
        else:
            unmatched_diary.append(diary_flight)

    unmatched_gps = [f for f in gps_flights if f[0] not in gps_matched_ids]

    print(f"\nMatching results:")
    print(f"  Matched pairs: {len(matched)}")
    print(f"  Unmatched diary entries: {len(unmatched_diary)}")
    print(f"  Unmatched GPS flights: {len(unmatched_gps)}")

    if dry_run:
        print("\n--- DRY RUN ---")
        print("\nMatched flights (first 10):")
        for diary, gps in matched[:10]:
            print(f"  {diary[1]} {diary[3]}->{diary[4]} (diary) <-> {gps[1]} (GPS)")

        if unmatched_diary:
            print(f"\nUnmatched diary entries (first 10):")
            for f in unmatched_diary[:10]:
                print(f"  {f[1]} {f[2] or 'N/A':8} {f[3]}->{f[4]}")

        if unmatched_gps:
            print(f"\nUnmatched GPS flights (first 10):")
            for f in unmatched_gps[:10]:
                print(f"  {f[1]} {f[3]}->{f[4]}")

        cur.close()
        conn.close()
        return

    print("\nMerging matched flights...")
    for diary_flight, gps_flight in matched:
        merge_flights(diary_flight, gps_flight, cur)

    conn.commit()

    cur.execute("SELECT source, COUNT(*) FROM flight GROUP BY source ORDER BY source")
    counts = cur.fetchall()
    print("\nFlight counts by source:")
    for source, count in counts:
        print(f"  {source}: {count}")

    cur.close()
    conn.close()

    print("\nMatching complete!")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Match flight diary with GPS flights')
    parser.add_argument('--dry-run', action='store_true', help='Show matches without updating')
    args = parser.parse_args()

    run_matching(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
