"""Places sync — propagate my-locations place definitions to journal entries."""

import math
from datetime import date

import psycopg2
from fastapi import APIRouter, Depends

from config.settings import settings
from src.api.deps import get_conn, get_current_user

router = APIRouter()


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
    dsn = settings.cross_dsn(
        settings.mylocation_db_name,
        settings.mylocation_db_user,
        settings.mylocation_db_password,
    )
    conn = psycopg2.connect(dsn)
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

    conn.commit()
    cur.close()
    return {"matched": updated, "cleared": cleared, "total_locations": len(rows), "total_places": len(places)}
