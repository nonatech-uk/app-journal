"""Places — manage my-locations places and sync to journal entries/events."""

import math
from datetime import date

import psycopg2
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.settings import settings
from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


def _get_mylocation_conn():
    return psycopg2.connect(settings.cross_dsn(
        settings.mylocation_db_name,
        settings.mylocation_db_user,
        settings.mylocation_db_password,
    ))


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two points."""
    R = 6_371_000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fetch_places() -> list[dict]:
    """Fetch all places from the mylocation database."""
    conn = _get_mylocation_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, lat, lon, distance_m, date_from, date_to FROM place ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "lat": r[2], "lon": r[3],
         "distance_m": r[4], "date_from": r[5], "date_to": r[6]}
        for r in rows
    ]


def _match_place(lat: float, lon: float, entry_date: date | None, places: list[dict]) -> dict | None:
    """Find the nearest place whose radius covers the given point, respecting date bounds."""
    best = None
    best_dist = float("inf")
    for p in places:
        # Date filtering
        if entry_date:
            if p["date_from"] and p["date_from"] > entry_date:
                continue
            if p["date_to"] and p["date_to"] < entry_date:
                continue
        dist = _haversine_m(lat, lon, p["lat"], p["lon"])
        if dist <= p["distance_m"] and dist < best_dist:
            best = p
            best_dist = dist
    return best


@router.post("/places/sync")
def sync_places(conn=Depends(get_conn), _user=Depends(get_current_user)):
    """Match journal entry locations against my-locations places and update place_id/place_label."""
    places = _fetch_places()

    cur = conn.cursor()
    cur.execute("""
        SELECT l.id, l.latitude, l.longitude, l.place_id,
               e.created_at::date
        FROM location l
        JOIN entry e ON e.id = l.entry_id
        WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
    """)
    rows = cur.fetchall()

    updated = 0
    cleared = 0
    for loc_id, lat, lon, current_place_id, entry_date in rows:
        match = _match_place(lat, lon, entry_date, places)
        if match:
            if current_place_id != match["id"]:
                cur.execute(
                    "UPDATE location SET place_id = %s, place_label = %s WHERE id = %s",
                    (match["id"], match["name"], loc_id),
                )
                updated += 1
        elif current_place_id is not None:
            cur.execute(
                "UPDATE location SET place_id = NULL, place_label = NULL WHERE id = %s",
                (loc_id,),
            )
            cleared += 1

    # Also sync event locations
    cur.execute("""
        SELECT id, latitude, longitude, place_id, event_date
        FROM event
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    event_rows = cur.fetchall()
    event_updated = 0
    event_cleared = 0
    for eid, lat, lon, current_place_id, event_date in event_rows:
        match = _match_place(lat, lon, event_date, places)
        if match:
            if current_place_id != match["id"]:
                cur.execute(
                    "UPDATE event SET place_id = %s, place_label = %s WHERE id = %s",
                    (match["id"], match["name"], eid),
                )
                event_updated += 1
        elif current_place_id is not None:
            cur.execute(
                "UPDATE event SET place_id = NULL, place_label = NULL WHERE id = %s",
                (eid,),
            )
            event_cleared += 1

    conn.commit()
    cur.close()
    return {
        "matched": updated, "cleared": cleared,
        "total_locations": len(rows), "total_places": len(places),
        "events_matched": event_updated, "events_cleared": event_cleared,
        "total_events": len(event_rows),
    }


# ---------------------------------------------------------------------------
# Place CRUD (writes to mylocation database)
# ---------------------------------------------------------------------------

class PlaceCreate(BaseModel):
    name: str
    place_type_id: int = 1
    latitude: float
    longitude: float
    distance_m: int = 200
    date_from: str | None = None
    date_to: str | None = None
    notes: str | None = None


class PlaceUpdate(BaseModel):
    name: str | None = None
    place_type_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_m: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    notes: str | None = None


@router.get("/places")
def list_places(_user=Depends(get_current_user)):
    """List all places from the mylocation database with their types."""
    conn = _get_mylocation_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, pt.name AS place_type, p.place_type_id,
               p.lat, p.lon, p.distance_m, p.date_from, p.date_to, p.notes
        FROM place p
        JOIN place_type pt ON pt.id = p.place_type_id
        ORDER BY p.name
    """)
    cols = [desc[0] for desc in cur.description]
    places = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"items": places, "total": len(places)}


@router.get("/places/types")
def list_place_types(_user=Depends(get_current_user)):
    """List available place types."""
    conn = _get_mylocation_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM place_type ORDER BY id")
    types = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return types


@router.post("/places", status_code=201)
def create_place(body: PlaceCreate, _user=Depends(require_admin)):
    """Create a new place in the mylocation database."""
    conn = _get_mylocation_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO place (name, place_type_id, lat, lon, distance_m, date_from, date_to, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        body.name, body.place_type_id, body.latitude, body.longitude,
        body.distance_m, body.date_from, body.date_to, body.notes,
    ))
    place_id = cur.fetchone()[0]
    conn.commit()

    cur.execute("""
        SELECT p.id, p.name, pt.name AS place_type, p.place_type_id,
               p.lat, p.lon, p.distance_m, p.date_from, p.date_to, p.notes
        FROM place p
        JOIN place_type pt ON pt.id = p.place_type_id
        WHERE p.id = %s
    """, (place_id,))
    cols = [desc[0] for desc in cur.description]
    place = dict(zip(cols, cur.fetchone()))
    cur.close()
    conn.close()
    return place


@router.put("/places/{place_id}")
def update_place(place_id: int, body: PlaceUpdate, _user=Depends(require_admin)):
    """Update a place in the mylocation database."""
    conn = _get_mylocation_conn()
    cur = conn.cursor()

    updates = []
    params = []
    for field, col in [("name", "name"), ("place_type_id", "place_type_id"),
                        ("latitude", "lat"), ("longitude", "lon"),
                        ("distance_m", "distance_m"), ("notes", "notes")]:
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{col} = %s")
            params.append(val)
    for field in ("date_from", "date_to"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)

    if not updates:
        cur.close()
        conn.close()
        return {"updated": False}

    params.append(place_id)
    cur.execute(f"UPDATE place SET {', '.join(updates)} WHERE id = %s", params)
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(404, "Place not found")
    conn.commit()

    cur.execute("""
        SELECT p.id, p.name, pt.name AS place_type, p.place_type_id,
               p.lat, p.lon, p.distance_m, p.date_from, p.date_to, p.notes
        FROM place p
        JOIN place_type pt ON pt.id = p.place_type_id
        WHERE p.id = %s
    """, (place_id,))
    cols = [desc[0] for desc in cur.description]
    place = dict(zip(cols, cur.fetchone()))
    cur.close()
    conn.close()
    return place


@router.delete("/places/{place_id}")
def delete_place(place_id: int, _user=Depends(require_admin)):
    """Delete a place from the mylocation database."""
    conn = _get_mylocation_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM place WHERE id = %s", (place_id,))
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(404, "Place not found")
    conn.commit()
    cur.close()
    conn.close()
    return {"deleted": True}
