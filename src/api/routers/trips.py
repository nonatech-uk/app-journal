"""Trip management — CRUD for trips, entry linking, stats."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


@router.get("/trips")
def list_trips(
    year: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if year:
        conditions.append("EXTRACT(YEAR FROM t.start_date) = %(year)s")
        params["year"] = year

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    cur.execute(f"""
        SELECT t.id, t.title, t.start_date, t.end_date, t.countries,
               t.locations, t.immich_album_id, t.cover_asset_id,
               (SELECT count(*) FROM trip_entry te WHERE te.trip_id = t.id) AS entry_count,
               (end_date - start_date + 1) AS duration_days
        FROM trip t
        {where}
        ORDER BY t.start_date DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)

    cols = [desc[0] for desc in cur.description]
    trips = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Total count
    cur.execute(f"SELECT count(*) FROM trip t {where}", params)
    total = cur.fetchone()[0]

    # Year summary for filtering
    cur.execute("SELECT EXTRACT(YEAR FROM start_date)::int AS y, count(*) FROM trip GROUP BY y ORDER BY y DESC")
    years = [{"year": r[0], "count": r[1]} for r in cur.fetchall()]

    return {"items": trips, "total": total, "years": years}


@router.get("/trips/{trip_id}")
def get_trip(trip_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.path::text, t.title, t.description, t.start_date, t.end_date,
               t.countries, t.locations, t.companions, t.cover_asset_id,
               t.immich_album_id, t.tags, t.notes, t.custom_stats,
               t.created_at, t.modified_at
        FROM trip t WHERE t.id = %s
    """, (trip_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Trip not found")

    cols = [desc[0] for desc in cur.description]
    trip = dict(zip(cols, row))

    # Linked entries
    cur.execute("""
        SELECT te.entry_id, te.day_number, te.day_label, te.is_travel_day, te.is_rest_day,
               e.created_at, e.uuid, left(e.markdown_text, 200) AS preview,
               l.place_name, l.country
        FROM trip_entry te
        JOIN entry e ON e.id = te.entry_id
        LEFT JOIN LATERAL (
            SELECT place_name, country FROM location WHERE entry_id = e.id
            ORDER BY CASE WHEN location_type = 'primary' THEN 0 ELSE 1 END
            LIMIT 1
        ) l ON true
        WHERE te.trip_id = %s
        ORDER BY e.created_at
    """, (trip_id,))
    entry_cols = [desc[0] for desc in cur.description]
    trip["entries"] = [dict(zip(entry_cols, r)) for r in cur.fetchall()]

    # Stats
    cur.execute("SELECT key, value, unit FROM trip_stat WHERE trip_id = %s ORDER BY key", (trip_id,))
    trip["stats"] = [{"key": r[0], "value": r[1], "unit": r[2]} for r in cur.fetchall()]

    # Events linked to this trip
    cur.execute("""
        SELECT e.id, e.title, e.event_date, e.end_date, et.name AS event_type, e.fuzzy_date, e.place_label
        FROM event e
        JOIN event_type et ON et.id = e.event_type_id
        WHERE e.trip_id = %s ORDER BY e.event_date
    """, (trip_id,))
    evt_cols = [desc[0] for desc in cur.description]
    trip["events"] = [dict(zip(evt_cols, r)) for r in cur.fetchall()]

    return trip


class TripUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    notes: str | None = None
    companions: list[str] | None = None
    tags: list[str] | None = None


@router.put("/trips/{trip_id}")
def update_trip(
    trip_id: int,
    body: TripUpdate,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM trip WHERE id = %s", (trip_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Trip not found")

    updates = []
    params = []
    for field in ("title", "description", "start_date", "end_date", "notes"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.companions is not None:
        updates.append("companions = %s")
        params.append(body.companions)
    if body.tags is not None:
        updates.append("tags = %s")
        params.append(body.tags)

    if not updates:
        return {"updated": False}

    updates.append("modified_at = now()")
    params.append(trip_id)
    cur.execute(f"UPDATE trip SET {', '.join(updates)} WHERE id = %s", params)
    conn.commit()
    return {"updated": True}
