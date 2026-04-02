#!/usr/bin/env python3
"""
Import flights from Apple Wallet boarding pass export (passes.json).

Parses Apple Wallet pass format, filters to Stuart's air boarding passes,
and inserts new flights with source='wallet'.

Usage:
    python scripts/wallet_import.py passes.json
    python scripts/wallet_import.py passes.json --dry-run
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from config.settings import settings
from src.services.flights.airports import haversine_km, load_airports


# Through-destinations that duplicate existing multi-leg entries
EXCLUDE = {
    (date(2019, 5, 22), 'LGW', 'GND'),  # DB has LGW->UVF + UVF->GND
}


def is_stuart(fields, back_fields):
    """Return True if this pass belongs to Stuart (not Frances Breslin)."""
    for key in ('passenger', 'passengerName', 'passenger-name', 'paxName'):
        name = (fields.get(key, '') or back_fields.get(key, '')).upper()
        if name:
            if 'BRESLIN' in name or 'FRANCES' in name:
                return False
            if 'BEVAN' in name or 'STUART' in name:
                return True
    return True


def get_fields(bp):
    """Collect fields from all sections. Back fields returned separately."""
    fields = {}
    for section in ('primaryFields', 'secondaryFields', 'auxiliaryFields', 'headerFields'):
        for f in bp.get(section, []):
            fields[f['key']] = f.get('value', '')
    back = {}
    for f in bp.get('backFields', []):
        back[f['key']] = f.get('value', '')
    return fields, back


def get_airport(fields, back_fields, direction):
    """Extract 3-letter IATA code for departure or arrival."""
    if direction == 'dep':
        candidates = ('origin', 'from', 'boardPoint', 'departure', 'depart')
        back_key = ('departure', 'from')
    else:
        candidates = ('destination', 'to', 'offPoint', 'arrival', 'arrive')
        back_key = ('arrival', 'to')

    for key in candidates:
        v = fields.get(key, '').strip()
        if v and len(v) == 3 and v.isalpha():
            return v.upper()

    for key in back_key:
        v = back_fields.get(key, '')
        if v:
            m = re.search(r'\(([A-Z]{3})\)', v)
            if m:
                return m.group(1)
            code = v.strip().split()[0]
            if len(code) == 3 and code.isalpha():
                return code.upper()

    return None


def get_flight_number(fields, back_fields):
    """Extract and normalise flight number (strip leading zeros from numeric part)."""
    for key in ('flightNumber', 'flight', 'Flight', 'flightNewName'):
        v = fields.get(key, '').strip()
        if v:
            return normalise_flight_number(v)
    v = back_fields.get('flightNumber', back_fields.get('flight', '')).strip()
    if v:
        return normalise_flight_number(v)
    return None


def normalise_flight_number(fn):
    """BA0028 -> BA28, SK4455 -> SK4455, FR 123 -> FR123."""
    fn = fn.replace(' ', '')
    m = re.match(r'^([A-Z]{2})0*(\d+)$', fn)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return fn


def get_date(fields, p):
    """Parse flight date from pass fields."""
    for key in ('departureDate', 'date', 'Date'):
        ds = fields.get(key, '').strip()
        if ds:
            for fmt in ('%d%b%y', '%d%b%Y', '%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y'):
                try:
                    return datetime.strptime(ds, fmt).date()
                except ValueError:
                    pass
            try:
                return datetime.fromisoformat(ds.replace('Z', '+00:00')).date()
            except (ValueError, TypeError):
                pass

    for key in ('departs', 'departure', 'depart'):
        ds = fields.get(key, '').strip()
        if ds:
            m = re.match(r'(\d{1,2})\s+(\w{3})\s*[-\u2013]\s*\d', ds)
            if m:
                rel = p.get('relevantDate', '')
                if rel:
                    try:
                        year = datetime.fromisoformat(rel.replace('Z', '+00:00')).year
                        return datetime.strptime(f"{m.group(1)} {m.group(2)} {year}", '%d %b %Y').date()
                    except (ValueError, TypeError):
                        pass

    rel = p.get('relevantDate', '')
    if rel:
        try:
            return datetime.fromisoformat(rel.replace('Z', '+00:00')).date()
        except (ValueError, TypeError):
            pass
    return None


def map_class(label):
    """Map class label to flight_class integer (1=economy, 2=business, 3=first, 4=economy-plus)."""
    if not label:
        return None
    low = label.lower().strip()
    if 'first' in low:
        return 3
    if any(k in low for k in ('business', 'club')):
        return 2
    if any(k in low for k in ('premium', 'plus', 'world traveller plus')):
        return 4
    if any(k in low for k in ('economy', 'traveller')):
        return 1
    return None


def extract_airline_code(flight_number):
    """Extract 2-letter airline code from flight number."""
    if flight_number:
        m = re.match(r'^([A-Z]{2})', flight_number)
        if m:
            return m.group(1)
    return None


def parse_passes(passes_path):
    """Parse passes.json and return list of flight dicts."""
    with open(passes_path) as f:
        passes = json.load(f)

    flights = []
    skipped_other = 0
    skipped_nodata = 0

    for p in passes:
        bp = p.get('boardingPass')
        if not bp or bp.get('transitType') != 'PKTransitTypeAir':
            continue

        fields, back = get_fields(bp)

        if not is_stuart(fields, back):
            skipped_other += 1
            continue

        dep = get_airport(fields, back, 'dep')
        arr = get_airport(fields, back, 'arr')
        flight_date = get_date(fields, p)

        if not dep or not arr or not flight_date:
            skipped_nodata += 1
            continue

        if len(dep) != 3 or len(arr) != 3 or dep.isdigit() or arr.isdigit():
            skipped_nodata += 1
            continue

        fn = get_flight_number(fields, back)
        seat = fields.get('seat', fields.get('Seat', '')).strip() or None

        cls_label = ''
        for key in ('class', 'classz', 'bookingClass'):
            v = fields.get(key, '').strip()
            if v:
                cls_label = v
                break
        if not cls_label:
            cls_label = back.get('serviceClass', '').strip()

        flights.append({
            'date': flight_date,
            'dep_airport': dep,
            'arr_airport': arr,
            'flight_number': fn,
            'seat_number': seat,
            'flight_class': map_class(cls_label),
            'airline': p.get('organizationName', ''),
            'airline_code': extract_airline_code(fn),
        })

    # Deduplicate on (date, dep, arr) — keep first occurrence
    seen = set()
    unique = []
    for f in sorted(flights, key=lambda x: x['date']):
        key = (f['date'], f['dep_airport'], f['arr_airport'])
        if key in EXCLUDE:
            continue
        if key not in seen:
            seen.add(key)
            unique.append(f)

    print(f"Parsed {len(flights)} Stuart passes, skipped {skipped_other} other-passenger, {skipped_nodata} incomplete")
    print(f"Unique flights after dedup: {len(unique)}")

    return unique


def import_wallet(passes_path, dry_run=False):
    """Import wallet passes into flight table."""
    flights = parse_passes(passes_path)
    airports = load_airports()

    conn = psycopg2.connect(settings.dsn)
    cur = conn.cursor()
    cur.execute("SELECT date, dep_airport, arr_airport FROM flight")
    existing = {(row[0], row[1], row[2]) for row in cur.fetchall()}
    cur.close()

    new_flights = []
    skipped_existing = 0
    for f in flights:
        key = (f['date'], f['dep_airport'], f['arr_airport'])
        if key in existing:
            skipped_existing += 1
        else:
            new_flights.append(f)

    print(f"Already in DB: {skipped_existing}, new to add: {len(new_flights)}")

    enriched = []
    for f in new_flights:
        dep_info = airports.get(f['dep_airport'], {})
        arr_info = airports.get(f['arr_airport'], {})

        dep_lat = dep_info.get('lat')
        dep_lon = dep_info.get('lon')
        arr_lat = arr_info.get('lat')
        arr_lon = arr_info.get('lon')

        distance_km = None
        if dep_lat and dep_lon and arr_lat and arr_lon:
            distance_km = haversine_km(dep_lat, dep_lon, arr_lat, arr_lon)

        enriched.append({
            'date': f['date'],
            'flight_number': f['flight_number'],
            'dep_airport': f['dep_airport'],
            'dep_airport_name': dep_info.get('name'),
            'dep_icao': dep_info.get('icao'),
            'arr_airport': f['arr_airport'],
            'arr_airport_name': arr_info.get('name'),
            'arr_icao': arr_info.get('icao'),
            'airline': f['airline'],
            'airline_code': f['airline_code'],
            'seat_number': f['seat_number'],
            'flight_class': f['flight_class'],
            'notes': 'Imported from Apple Wallet',
            'source': 'wallet',
            'gps_matched': False,
            'dep_lat': dep_lat,
            'dep_lon': dep_lon,
            'arr_lat': arr_lat,
            'arr_lon': arr_lon,
            'distance_km': distance_km,
        })

    if dry_run:
        print(f"\nDry run — {len(enriched)} flights to insert:\n")
        for f in enriched:
            cls = {1: 'Y', 2: 'J', 3: 'F', 4: 'W'}.get(f['flight_class'], '?')
            print(f"  {f['date']}  {f['dep_airport']}->{f['arr_airport']}  "
                  f"{f['flight_number'] or '?':>8}  {f['airline']:<25}  "
                  f"seat:{f['seat_number'] or '-':>4}  class:{cls}  "
                  f"{f['distance_km'] or '?'}km")
        conn.close()
        return enriched

    cur = conn.cursor()

    sql = """
        INSERT INTO flight (
            date, flight_number, dep_airport, dep_airport_name, dep_icao,
            arr_airport, arr_airport_name, arr_icao, airline, airline_code,
            seat_number, flight_class, notes, source, gps_matched,
            dep_lat, dep_lon, arr_lat, arr_lon, distance_km
        ) VALUES (
            %(date)s, %(flight_number)s, %(dep_airport)s, %(dep_airport_name)s, %(dep_icao)s,
            %(arr_airport)s, %(arr_airport_name)s, %(arr_icao)s, %(airline)s, %(airline_code)s,
            %(seat_number)s, %(flight_class)s, %(notes)s, %(source)s, %(gps_matched)s,
            %(dep_lat)s, %(dep_lon)s, %(arr_lat)s, %(arr_lon)s, %(distance_km)s
        )
        ON CONFLICT (date, dep_airport, arr_airport, COALESCE(flight_number, '')) DO NOTHING
    """

    inserted = 0
    errors = 0

    for flight in enriched:
        try:
            cur.execute(sql, flight)
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"Error: {flight['date']} {flight['dep_airport']}->{flight['arr_airport']}: {e}")
            errors += 1
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nInserted {inserted} new flights, {len(enriched) - inserted - errors} duplicates skipped, {errors} errors")
    return enriched


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import Apple Wallet boarding passes to flights DB')
    parser.add_argument('passes_file', help='Path to passes.json')
    parser.add_argument('--dry-run', action='store_true', help='Parse and display but do not insert')
    args = parser.parse_args()

    import_wallet(args.passes_file, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
