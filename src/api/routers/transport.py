"""Transport — list/detail/ingest for flights, GA flights, and rail journeys."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config.settings import settings
from src.api.deps import get_conn, get_current_user, require_admin
from src.services.flights.images import (
    aircraft_image_path,
    has_aircraft_image,
    has_route_image,
    route_image_path,
    schedule_prefetch,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pipeline auth
# ---------------------------------------------------------------------------

def _check_pipeline_auth(authorization: str = Header(...)):
    if not settings.pipeline_secret:
        raise HTTPException(503, "Pipeline endpoint not configured")
    if not authorization.startswith("Bearer "):
        raise HTTPException(403, "Invalid credentials")
    if not secrets.compare_digest(authorization[7:], settings.pipeline_secret):
        raise HTTPException(403, "Invalid credentials")


# ---------------------------------------------------------------------------
# Flight ingest (from pipeline)
# ---------------------------------------------------------------------------

_CABIN_CLASS_MAP = {"economy": 1, "business": 2, "first": 3}


class FlightIngest(BaseModel):
    date: str
    dep_airport: str
    arr_airport: str
    flight_number: str | None = None
    airline: str | None = None
    seat_number: str | None = None
    cabin_class: str | None = None
    source: str = "pipeline"


@router.post("/flights/ingest")
def ingest_flight(
    body: FlightIngest,
    conn=Depends(get_conn),
    _=Depends(_check_pipeline_auth),
):
    """Ingest a flight record from the pipeline."""
    cur = conn.cursor()
    flight_class = _CABIN_CLASS_MAP.get((body.cabin_class or "").lower())
    cur.execute("""
        INSERT INTO flight (date, dep_airport, arr_airport, flight_number,
                            airline, seat_number, flight_class, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date, dep_airport, arr_airport, COALESCE(flight_number, '')) DO NOTHING
        RETURNING id
    """, (body.date, body.dep_airport, body.arr_airport, body.flight_number,
          body.airline, body.seat_number, flight_class, body.source))
    row = cur.fetchone()
    conn.commit()
    if row:
        return {"status": "created", "id": row[0]}
    return {"status": "duplicate"}


# ---------------------------------------------------------------------------
# Commercial Flights
# ---------------------------------------------------------------------------

@router.get("/flights")
def list_flights(
    year: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = ["is_route = FALSE"]
    params: dict = {"limit": limit, "offset": offset}

    if year:
        conditions.append("EXTRACT(YEAR FROM date) = %(year)s")
        params["year"] = year

    where = "WHERE " + " AND ".join(conditions)

    cur.execute(f"""
        SELECT id, date, flight_number, dep_airport, dep_airport_name,
               arr_airport, arr_airport_name, dep_time, arr_time, duration,
               airline, aircraft_type, registration, seat_number,
               flight_class, distance_km, source,
               dep_lat, dep_lon, arr_lat, arr_lon
        FROM flight
        {where}
        ORDER BY date DESC, dep_time NULLS LAST
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    cols = [desc[0] for desc in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Add image availability flags and schedule prefetch
    for item in items:
        item["has_route_image"] = has_route_image(item["dep_airport"], item["arr_airport"])
        item["has_aircraft_image"] = has_aircraft_image(item.get("registration"))
    schedule_prefetch(items)

    cur.execute(f"SELECT count(*) FROM flight {where}", params)
    total = cur.fetchone()[0]

    cur.execute("SELECT EXTRACT(YEAR FROM date)::int AS y, count(*) FROM flight WHERE is_route = FALSE GROUP BY y ORDER BY y DESC")
    years = [{"year": r[0], "count": r[1]} for r in cur.fetchall()]

    return {"items": items, "total": total, "years": years}


@router.get("/flights/{flight_id}")
def get_flight(flight_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date, flight_number, dep_airport, dep_airport_name, dep_icao,
               arr_airport, arr_airport_name, arr_icao,
               dep_time, arr_time, duration,
               airline, airline_code, aircraft_type, aircraft_code, registration,
               seat_number, seat_type, flight_class, flight_reason,
               notes, source, gps_matched,
               dep_lat, dep_lon, arr_lat, arr_lon,
               distance_km, gate_origin, gate_destination,
               terminal_origin, terminal_destination, baggage_claim,
               departure_delay, arrival_delay, codeshares
        FROM flight WHERE id = %s
    """, (flight_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Flight not found")
    cols = [desc[0] for desc in cur.description]
    flight = dict(zip(cols, row))
    flight["has_route_image"] = has_route_image(flight.get("dep_airport"), flight.get("arr_airport"))
    flight["has_aircraft_image"] = has_aircraft_image(flight.get("registration"))
    return flight


# ---------------------------------------------------------------------------
# GA Flights
# ---------------------------------------------------------------------------

@router.get("/ga-flights")
def list_ga_flights(
    year: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if year:
        conditions.append("EXTRACT(YEAR FROM date) = %(year)s")
        params["year"] = year

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    cur.execute(f"""
        SELECT id, date, aircraft_type, registration, captain,
               operating_capacity, dep_airport, arr_airport,
               dep_time, arr_time, hours_total, exercise, comments
        FROM ga_flight
        {where}
        ORDER BY date DESC, dep_time NULLS LAST
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    cols = [desc[0] for desc in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(f"SELECT count(*) FROM ga_flight {where}", params)
    total = cur.fetchone()[0]

    cur.execute("SELECT EXTRACT(YEAR FROM date)::int AS y, count(*) FROM ga_flight GROUP BY y ORDER BY y DESC")
    years = [{"year": r[0], "count": r[1]} for r in cur.fetchall()]

    return {"items": items, "total": total, "years": years}


@router.get("/ga-flights/{flight_id}")
def get_ga_flight(flight_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("SELECT * FROM ga_flight WHERE id = %s", (flight_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "GA flight not found")
    cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


# ---------------------------------------------------------------------------
# Rail Journeys
# ---------------------------------------------------------------------------

@router.get("/rail-journeys")
def list_rail_journeys(
    year: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if year:
        conditions.append("EXTRACT(YEAR FROM date) = %(year)s")
        params["year"] = year

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    cur.execute(f"""
        SELECT id, date, time, from_station, from_code, to_station, to_code,
               operator, ticket_type, direction, train, via, price, currency
        FROM rail_journey
        {where}
        ORDER BY date DESC, time NULLS LAST
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    cols = [desc[0] for desc in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(f"SELECT count(*) FROM rail_journey {where}", params)
    total = cur.fetchone()[0]

    cur.execute("SELECT EXTRACT(YEAR FROM date)::int AS y, count(*) FROM rail_journey GROUP BY y ORDER BY y DESC")
    years = [{"year": r[0], "count": r[1]} for r in cur.fetchall()]

    return {"items": items, "total": total, "years": years}


@router.get("/rail-journeys/{journey_id}")
def get_rail_journey(journey_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("SELECT * FROM rail_journey WHERE id = %s", (journey_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Rail journey not found")
    cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


# ---------------------------------------------------------------------------
# Flight Images
# ---------------------------------------------------------------------------

@router.get("/flights/{flight_id}/images/{image_type}/{size}")
def get_flight_image(
    flight_id: int,
    image_type: str,
    size: str,
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    if image_type not in ("route", "aircraft"):
        raise HTTPException(400, "image_type must be 'route' or 'aircraft'")
    if size not in ("thumb", "full"):
        raise HTTPException(400, "size must be 'thumb' or 'full'")

    cur = conn.cursor()
    cur.execute("SELECT dep_airport, arr_airport, registration FROM flight WHERE id = %s", (flight_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Flight not found")

    if image_type == "route":
        path = route_image_path(row[0], row[1], size)
        media_type = "image/png"
    else:
        if not row[2]:
            raise HTTPException(404, "No registration for this flight")
        path = aircraft_image_path(row[2], size)
        media_type = "image/jpeg"

    if not path.exists():
        raise HTTPException(404, "Image not yet available",
                            headers={"Cache-Control": "no-store"})

    return FileResponse(path, media_type=media_type,
                        headers={"Cache-Control": "public, max-age=86400"})


@router.post("/flights/images/prefetch-all")
def prefetch_all_images(
    conn=Depends(get_conn),
    _=Depends(require_admin),
):
    """Trigger background prefetch for all flights missing images."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, dep_airport, arr_airport, dep_lat, dep_lon,
               arr_lat, arr_lon, registration
        FROM flight
    """)
    cols = [desc[0] for desc in cur.description]
    batch = [dict(zip(cols, r)) for r in cur.fetchall()]
    schedule_prefetch(batch)
    return {"status": "prefetch_scheduled", "count": len(batch)}
