#!/usr/bin/env python3
"""
Import MyFlightDiary.com CSV export to flight database table.

Parses the flightdiary CSV format and inserts flights with source='flightdiary'.
Looks up airport coordinates from OpenFlights database.

Usage:
    python scripts/flight_import.py flightdiary_export.csv
    python scripts/flight_import.py flightdiary_export.csv --dry-run
"""

import csv
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from config.settings import settings
from src.services.flights.airports import haversine_km, load_airports


def parse_airport_string(airport_str):
    """Parse airport string like "London / Heathrow (LHR/EGLL)".

    Returns: (iata, icao, name) tuple
    """
    if not airport_str:
        return None, None, None

    match = re.search(r'\(([A-Z]{3})(?:/([A-Z]{4}))?\)', airport_str)
    if match:
        iata = match.group(1)
        icao = match.group(2)
        name = airport_str[:match.start()].strip()
        return iata, icao, name

    return None, None, airport_str


def parse_airline_string(airline_str):
    """Parse airline string like "British Airways (BA/BAW)".

    Returns: (name, code) tuple
    """
    if not airline_str:
        return None, None

    match = re.search(r'\(([A-Z0-9]{2})(?:/[A-Z]{3})?\)', airline_str)
    if match:
        code = match.group(1)
        name = airline_str[:match.start()].strip()
        return name, code

    return airline_str, None


def parse_aircraft_string(aircraft_str):
    """Parse aircraft string like "Boeing 777-200 (B772)".

    Returns: (type_name, code) tuple
    """
    if not aircraft_str:
        return None, None

    match = re.search(r'\(([A-Z0-9]+)\)', aircraft_str)
    if match:
        code = match.group(1)
        name = aircraft_str[:match.start()].strip()
        return name, code

    return aircraft_str, None


def parse_duration(duration_str):
    """Parse duration string like "13:15:00" to PostgreSQL interval format."""
    if not duration_str:
        return None

    parts = duration_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        return f"{hours} hours {minutes} minutes"

    return None


def parse_time(time_str):
    """Parse time string like "23:30:00" to time object."""
    if not time_str:
        return None

    try:
        return datetime.strptime(time_str, "%H:%M:%S").time()
    except ValueError:
        return None


def import_flightdiary(csv_path, dry_run=False):
    """Import flights from MyFlightDiary.com CSV export."""
    airports = load_airports()

    flights = []
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        header_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('Date,') or line.strip().startswith('"Date"'):
                header_idx = i
                break

        reader = csv.DictReader(lines[header_idx:])

        for row in reader:
            if not row.get('Date') or not row.get('From') or not row.get('To'):
                skipped += 1
                continue

            dep_iata, dep_icao, dep_name = parse_airport_string(row['From'])
            arr_iata, arr_icao, arr_name = parse_airport_string(row['To'])

            if not dep_iata or not arr_iata:
                print(f"Warning: Could not parse airports for row: {row['Date']} {row['From']} -> {row['To']}")
                skipped += 1
                continue

            airline_name, airline_code = parse_airline_string(row.get('Airline', ''))
            aircraft_type, aircraft_code = parse_aircraft_string(row.get('Aircraft', ''))

            seat_type = None
            seat_type_raw = row.get('Seat type', '')
            if seat_type_raw:
                try:
                    seat_type = int(seat_type_raw)
                except ValueError:
                    pass

            flight_class = None
            flight_class_raw = row.get('Flight class', '')
            if flight_class_raw:
                try:
                    flight_class = int(flight_class_raw)
                except ValueError:
                    pass

            flight_reason = None
            flight_reason_raw = row.get('Flight reason', '')
            if flight_reason_raw:
                try:
                    flight_reason = int(flight_reason_raw)
                except ValueError:
                    pass

            dep_coords = airports.get(dep_iata, {})
            arr_coords = airports.get(arr_iata, {})

            dep_lat = dep_coords.get('lat')
            dep_lon = dep_coords.get('lon')
            arr_lat = arr_coords.get('lat')
            arr_lon = arr_coords.get('lon')

            distance_km = None
            if dep_lat and dep_lon and arr_lat and arr_lon:
                distance_km = haversine_km(dep_lat, dep_lon, arr_lat, arr_lon)

            if not dep_name and dep_iata in airports:
                dep_name = airports[dep_iata]['name']
            if not arr_name and arr_iata in airports:
                arr_name = airports[arr_iata]['name']

            flight = {
                'date': row['Date'],
                'flight_number': row.get('Flight number', '').strip() or None,
                'dep_airport': dep_iata,
                'dep_airport_name': dep_name,
                'dep_icao': dep_icao,
                'arr_airport': arr_iata,
                'arr_airport_name': arr_name,
                'arr_icao': arr_icao,
                'dep_time': parse_time(row.get('Dep time', '')),
                'arr_time': parse_time(row.get('Arr time', '')),
                'duration': parse_duration(row.get('Duration', '')),
                'airline': airline_name,
                'airline_code': airline_code,
                'aircraft_type': aircraft_type,
                'aircraft_code': aircraft_code,
                'registration': row.get('Registration', '').strip() or None,
                'seat_number': row.get('Seat number', '').strip() or None,
                'seat_type': seat_type,
                'flight_class': flight_class,
                'flight_reason': flight_reason,
                'notes': row.get('Note', '').strip() or None,
                'source': 'flightdiary',
                'gps_matched': False,
                'dep_lat': dep_lat,
                'dep_lon': dep_lon,
                'arr_lat': arr_lat,
                'arr_lon': arr_lon,
                'distance_km': distance_km,
            }

            flights.append(flight)

    print(f"Parsed {len(flights)} flights, skipped {skipped}")

    if dry_run:
        print("\nDry run - first 5 flights:")
        for f in flights[:5]:
            print(f"  {f['date']} {f['flight_number'] or 'N/A':8} {f['dep_airport']}->{f['arr_airport']} ({f['distance_km'] or '?'}km) {f['airline'] or 'Unknown'}")
        return flights

    conn = psycopg2.connect(settings.dsn)
    cur = conn.cursor()

    sql = """
        INSERT INTO flight (
            date, flight_number, dep_airport, dep_airport_name, dep_icao,
            arr_airport, arr_airport_name, arr_icao, dep_time, arr_time,
            duration, airline, airline_code, aircraft_type, aircraft_code,
            registration, seat_number, seat_type, flight_class, flight_reason,
            notes, source, gps_matched, dep_lat, dep_lon, arr_lat, arr_lon, distance_km
        ) VALUES (
            %(date)s, %(flight_number)s, %(dep_airport)s, %(dep_airport_name)s, %(dep_icao)s,
            %(arr_airport)s, %(arr_airport_name)s, %(arr_icao)s, %(dep_time)s, %(arr_time)s,
            %(duration)s, %(airline)s, %(airline_code)s, %(aircraft_type)s, %(aircraft_code)s,
            %(registration)s, %(seat_number)s, %(seat_type)s, %(flight_class)s, %(flight_reason)s,
            %(notes)s, %(source)s, %(gps_matched)s, %(dep_lat)s, %(dep_lon)s, %(arr_lat)s, %(arr_lon)s, %(distance_km)s
        )
        ON CONFLICT (date, dep_airport, arr_airport, COALESCE(flight_number, '')) DO UPDATE SET
            dep_airport_name = EXCLUDED.dep_airport_name,
            arr_airport_name = EXCLUDED.arr_airport_name,
            airline = EXCLUDED.airline,
            aircraft_type = EXCLUDED.aircraft_type,
            registration = EXCLUDED.registration,
            seat_number = EXCLUDED.seat_number,
            notes = EXCLUDED.notes
    """

    inserted = 0
    errors = 0

    for flight in flights:
        try:
            cur.execute(sql, flight)
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"Error inserting {flight['date']} {flight['dep_airport']}->{flight['arr_airport']}: {e}")
            errors += 1
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nInserted/updated {inserted} flights, {errors} errors")
    return flights


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import MyFlightDiary.com CSV to database')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Parse but do not insert')
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    print(f"Importing from: {csv_path}")
    import_flightdiary(csv_path, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
