"""Enrich pipeline-ingested flights with FlightAware AeroAPI and OpenFlights data."""

import logging
import time
from datetime import datetime, timedelta

import httpx

from src.services.flights.aircraft import lookup_aircraft
from src.services.flights.airports import haversine_km, lookup_airport

log = logging.getLogger(__name__)

FLIGHTAWARE_URL = "https://aeroapi.flightaware.com/aeroapi"


def fetch_flight(api_key, flight_number, flight_date):
    """Look up a flight on FlightAware AeroAPI. Returns response dict or None."""
    date_obj = datetime.strptime(flight_date, "%Y-%m-%d")
    next_day = date_obj + timedelta(days=1)

    resp = httpx.get(
        f"{FLIGHTAWARE_URL}/flights/{flight_number}",
        headers={"x-apikey": api_key},
        params={
            "start": f"{flight_date}T00:00:00Z",
            "end": next_day.strftime("%Y-%m-%dT00:00:00Z"),
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = data.get("flights", [])
    if not results:
        return None

    for r in results:
        scheduled = r.get("scheduled_out") or ""
        if scheduled.startswith(flight_date):
            return r

    return results[0]


def fetch_flight_by_route(api_key, dep_icao, arr_icao, flight_date, scheduled_dep_local):
    """Fall back to route search when flight number lookup fails.

    Searches FlightAware for flights between two airports on a date,
    then matches by scheduled departure time (within 30 min tolerance).
    """
    date_obj = datetime.strptime(flight_date, "%Y-%m-%d")
    next_day = date_obj + timedelta(days=1)

    resp = httpx.get(
        f"{FLIGHTAWARE_URL}/airports/{dep_icao}/flights/to/{arr_icao}",
        headers={"x-apikey": api_key},
        params={
            "start": f"{flight_date}T00:00:00Z",
            "end": next_day.strftime("%Y-%m-%dT00:00:00Z"),
            "type": "Airline",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    candidates = []
    for entry in data.get("flights", []):
        for seg in entry.get("segments", [entry]):
            candidates.append(seg)

    if not candidates:
        return None

    dep_parts = scheduled_dep_local.split(":")
    dep_local_minutes = int(dep_parts[0]) * 60 + int(dep_parts[1])

    best = None
    best_diff = 9999
    for c in candidates:
        sched = c.get("scheduled_out") or ""
        if not sched:
            continue
        try:
            sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
            tz_name = c.get("origin", {}).get("timezone")
            if tz_name:
                from zoneinfo import ZoneInfo
                sched_local = sched_dt.astimezone(ZoneInfo(tz_name))
            else:
                sched_local = sched_dt
            sched_minutes = sched_local.hour * 60 + sched_local.minute
            diff = abs(sched_minutes - dep_local_minutes)
            if diff < best_diff:
                best_diff = diff
                best = c
        except (ValueError, TypeError):
            continue

    if best and best_diff <= 30:
        return best

    return None


def extract_time(time_str):
    """Extract HH:MM time from an ISO datetime string."""
    if not time_str:
        return None
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def calculate_duration(dep_time, arr_time):
    """Calculate duration string from two HH:MM times."""
    if not dep_time or not arr_time:
        return None
    try:
        dep = datetime.strptime(dep_time, "%H:%M")
        arr = datetime.strptime(arr_time, "%H:%M")
        diff = arr - dep
        if diff.total_seconds() < 0:
            diff += timedelta(days=1)
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes = remainder // 60
        return f"{hours:02d}:{minutes:02d}:00"
    except (ValueError, TypeError):
        return None


def apply_flightaware(updates, result, flight_number):
    """Extract FlightAware fields into the updates dict."""
    if result.get("aircraft_type"):
        updates["aircraft_code"] = result["aircraft_type"]
        ac = lookup_aircraft(result["aircraft_type"])
        if ac:
            updates["aircraft_type"] = ac["name"]
    if result.get("registration"):
        updates["registration"] = result["registration"]
    if result.get("operator_iata"):
        updates["airline_code"] = result["operator_iata"]
    if result.get("operator"):
        updates["airline"] = result["operator"]

    dep_time = extract_time(result.get("actual_off") or result.get("scheduled_out"))
    arr_time = extract_time(result.get("actual_on") or result.get("scheduled_in"))
    if dep_time:
        updates["dep_time"] = dep_time
    if arr_time:
        updates["arr_time"] = arr_time
    if dep_time and arr_time:
        dur = calculate_duration(dep_time, arr_time)
        if dur:
            updates["duration"] = dur

    if result.get("gate_origin"):
        updates["gate_origin"] = result["gate_origin"]
    if result.get("gate_destination"):
        updates["gate_destination"] = result["gate_destination"]
    if result.get("terminal_origin"):
        updates["terminal_origin"] = result["terminal_origin"]
    if result.get("terminal_destination"):
        updates["terminal_destination"] = result["terminal_destination"]
    if result.get("baggage_claim"):
        updates["baggage_claim"] = result["baggage_claim"]

    if result.get("departure_delay") is not None:
        updates["departure_delay"] = result["departure_delay"]
    if result.get("arrival_delay") is not None:
        updates["arrival_delay"] = result["arrival_delay"]
    if result.get("route_distance"):
        updates["route_distance"] = result["route_distance"]
    if result.get("actual_runway_off"):
        updates["runway_origin"] = result["actual_runway_off"]
    if result.get("actual_runway_on"):
        updates["runway_destination"] = result["actual_runway_on"]

    codeshares_iata = result.get("codeshares_iata") or []
    codeshares_iata = [c for c in codeshares_iata if c != flight_number]
    if codeshares_iata:
        updates["codeshares"] = ",".join(codeshares_iata)


def enrich_flight(conn, flight, api_key):
    """Enrich a single flight row with FlightAware + OpenFlights data.

    Returns a dict with 'status' ('enriched', 'no_fa_data', 'error') and 'summary'.
    """
    flight_id = flight[0]
    flight_date = str(flight[1])
    flight_number = flight[2]
    dep_iata = flight[3]
    arr_iata = flight[4]
    dep_time_db = str(flight[5]) if flight[5] else None

    log.info("  Enriching flight %d: %s %s→%s on %s", flight_id, flight_number, dep_iata, arr_iata, flight_date)

    updates = {}
    fa_found = False

    # OpenFlights enrichment (always available)
    dep = lookup_airport(dep_iata)
    arr = lookup_airport(arr_iata)

    if dep:
        updates["dep_airport_name"] = dep["name"]
        updates["dep_icao"] = dep["icao"]
        updates["dep_lat"] = dep["lat"]
        updates["dep_lon"] = dep["lon"]

    if arr:
        updates["arr_airport_name"] = arr["name"]
        updates["arr_icao"] = arr["icao"]
        updates["arr_lat"] = arr["lat"]
        updates["arr_lon"] = arr["lon"]

    if dep and arr:
        updates["distance_km"] = haversine_km(dep["lat"], dep["lon"], arr["lat"], arr["lon"])

    # FlightAware enrichment
    if api_key and flight_number:
        try:
            time.sleep(6)  # rate limit: 10 req/min
            result = fetch_flight(api_key, flight_number, flight_date)

            if not result and dep and arr and dep_time_db:
                log.info("    Flight number not found, trying route search %s→%s...", dep["icao"], arr["icao"])
                time.sleep(6)
                result = fetch_flight_by_route(api_key, dep["icao"], arr["icao"], flight_date, dep_time_db)
                if result:
                    log.info("    Route search matched: %s (operator: %s)", result.get("ident_iata"), result.get("operator"))

            if result:
                apply_flightaware(updates, result, flight_number)
                fa_found = True
                log.info("    FlightAware: aircraft=%s, reg=%s", result.get("aircraft_type"), result.get("registration"))
            else:
                log.info("    FlightAware: no results")
        except Exception as e:
            log.error("    FlightAware error: %s", e)
            return {"status": "error", "summary": f"{flight_number} {dep_iata}→{arr_iata}: {e}"}

    if not updates:
        log.info("    No enrichment data found")
        return {"status": "no_fa_data", "summary": f"{flight_number} {dep_iata}→{arr_iata}: no data found"}

    # Build UPDATE query
    set_clauses = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["id"] = flight_id
    sql = f"UPDATE flight SET {set_clauses} WHERE id = %(id)s"

    cur = conn.cursor()
    cur.execute(sql, updates)
    conn.commit()
    cur.close()

    field_count = len(updates) - 1  # exclude 'id'
    log.info("    Updated %d fields", field_count)

    summary = f"{flight_number} {dep_iata}→{arr_iata} {flight_date}"
    if fa_found:
        reg = updates.get("registration", "?")
        ac = updates.get("aircraft_code", "?")
        summary += f" — {ac} {reg}, {field_count} fields"
        return {"status": "enriched", "summary": summary}
    else:
        summary += f" — OpenFlights only ({field_count} fields), no FlightAware data"
        return {"status": "no_fa_data", "summary": summary}


def run_enrichment(conn, api_key, dry_run=False):
    """Run enrichment on all pending pipeline flights.

    Returns dict with keys: total, enriched, no_fa_data, errors, summaries.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date, flight_number, dep_airport, arr_airport, dep_time
        FROM flight
        WHERE source = 'pipeline'
          AND (dep_airport_name IS NULL OR registration IS NULL OR aircraft_type IS NULL)
          AND date >= CURRENT_DATE - INTERVAL '7 days'
          AND date < CURRENT_DATE
        ORDER BY date
    """)
    flights = cur.fetchall()
    cur.close()

    log.info("Found %d flight(s) to enrich", len(flights))

    if dry_run:
        log.info("Dry run — not enriching")
        return {"total": len(flights), "enriched": 0, "no_fa_data": 0, "errors": 0, "summaries": []}

    enriched = 0
    no_fa_data = 0
    errors = 0
    summaries = []

    for flight in flights:
        result = enrich_flight(conn, flight, api_key)
        summaries.append(result["summary"])
        if result["status"] == "enriched":
            enriched += 1
        elif result["status"] == "no_fa_data":
            no_fa_data += 1
        else:
            errors += 1

    return {
        "total": len(flights),
        "enriched": enriched,
        "no_fa_data": no_fa_data,
        "errors": errors,
        "summaries": summaries,
    }


def run_backfill(conn, api_key, dry_run=False):
    """Backfill all flights that have a flight number but missing registration or aircraft type.

    Returns dict with keys: total, enriched, no_fa_data, errors, summaries.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date, flight_number, dep_airport, arr_airport, dep_time
        FROM flight
        WHERE flight_number IS NOT NULL
          AND (registration IS NULL OR aircraft_type IS NULL)
        ORDER BY date DESC
    """)
    flights = cur.fetchall()
    cur.close()

    log.info("Backfill: found %d flight(s) with gaps", len(flights))

    if dry_run:
        for f in flights:
            log.info("  %s %s %s→%s", f[1], f[2], f[3], f[4])
        return {"total": len(flights), "enriched": 0, "no_fa_data": 0, "errors": 0, "summaries": []}

    enriched = 0
    no_fa_data = 0
    errors = 0
    summaries = []

    for flight in flights:
        result = enrich_flight(conn, flight, api_key)
        summaries.append(result["summary"])
        if result["status"] == "enriched":
            enriched += 1
        elif result["status"] == "no_fa_data":
            no_fa_data += 1
        else:
            errors += 1

    return {
        "total": len(flights),
        "enriched": enriched,
        "no_fa_data": no_fa_data,
        "errors": errors,
        "summaries": summaries,
    }
