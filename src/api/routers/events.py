"""Events — standalone life-event records (meals, shows, lectures, etc.)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config.settings import settings
from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    title: str
    event_date: str
    end_date: str | None = None
    event_type: str = "other"
    notes: str | None = None
    fuzzy_date: bool = False
    latitude: float | None = None
    longitude: float | None = None
    place_id: int | None = None
    trip_id: int | None = None
    documents: list[dict] | None = None  # [{"paperless_id": int, "label": str|None}]


class EventUpdate(BaseModel):
    title: str | None = None
    event_date: str | None = None
    end_date: str | None = None
    event_type: str | None = None
    notes: str | None = None
    fuzzy_date: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_id: int | None = -1  # sentinel: -1 means "not provided", None means "unlink"
    trip_id: int | None = -1  # sentinel: -1 means "not provided", None means "unlink"


class DocumentLink(BaseModel):
    paperless_id: int
    label: str | None = None


class EventTypeCreate(BaseModel):
    name: str


class EventTypeUpdate(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_event_type_id(cur, event_type: str) -> int:
    """Resolve an event_type name to its ID, raising 400 if not found."""
    cur.execute("SELECT id FROM event_type WHERE name = %s", (event_type,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(400, f"Unknown event type: {event_type}")
    return row[0]


def _resolve_place(place_id: int) -> dict | None:
    """Look up a place from the mylocation database. Returns {id, name, lat, lon} or None."""
    import psycopg2
    try:
        conn = psycopg2.connect(settings.cross_dsn(
            settings.mylocation_db_name,
            settings.mylocation_db_user,
            settings.mylocation_db_password,
        ))
        cur = conn.cursor()
        cur.execute("SELECT id, name, lat, lon FROM place WHERE id = %s", (place_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"id": row[0], "name": row[1], "lat": row[2], "lon": row[3]}
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Event Type CRUD
# ---------------------------------------------------------------------------

@router.get("/event-types")
def list_event_types(conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT et.id, et.name, count(e.id) AS event_count
        FROM event_type et
        LEFT JOIN event e ON e.event_type_id = et.id
        GROUP BY et.id, et.name
        ORDER BY et.name
    """)
    return [{"id": r[0], "name": r[1], "event_count": r[2]} for r in cur.fetchall()]


@router.post("/event-types", status_code=201)
def create_event_type(body: EventTypeCreate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    name = body.name.strip().lower()
    if not name:
        raise HTTPException(400, "Event type name cannot be empty")
    cur.execute("SELECT id FROM event_type WHERE name = %s", (name,))
    if cur.fetchone():
        raise HTTPException(409, f"Event type '{name}' already exists")
    cur.execute("INSERT INTO event_type (name) VALUES (%s) RETURNING id", (name,))
    type_id = cur.fetchone()[0]
    conn.commit()
    return {"id": type_id, "name": name, "event_count": 0}


@router.put("/event-types/{type_id}")
def update_event_type(type_id: int, body: EventTypeUpdate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    name = body.name.strip().lower()
    if not name:
        raise HTTPException(400, "Event type name cannot be empty")
    cur.execute("SELECT id FROM event_type WHERE name = %s AND id != %s", (name, type_id))
    if cur.fetchone():
        raise HTTPException(409, f"Event type '{name}' already exists")
    cur.execute("UPDATE event_type SET name = %s WHERE id = %s", (name, type_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Event type not found")
    conn.commit()
    return {"id": type_id, "name": name}


@router.delete("/event-types/{type_id}")
def delete_event_type(type_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM event WHERE event_type_id = %s", (type_id,))
    count = cur.fetchone()[0]
    if count > 0:
        raise HTTPException(409, f"Cannot delete: {count} events still use this type")
    cur.execute("DELETE FROM event_type WHERE id = %s", (type_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Event type not found")
    conn.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Event Endpoints
# ---------------------------------------------------------------------------

@router.get("/events")
def list_events(
    year: int | None = Query(None),
    event_type: str | None = Query(None),
    trip_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = ["e.deleted_at IS NULL"]
    params: dict = {"limit": limit, "offset": offset}

    if year:
        conditions.append("EXTRACT(YEAR FROM e.event_date) = %(year)s")
        params["year"] = year
    if event_type:
        conditions.append("et.name = %(event_type)s")
        params["event_type"] = event_type
    if trip_id is not None:
        conditions.append("e.trip_id = %(trip_id)s")
        params["trip_id"] = trip_id

    where = "WHERE " + " AND ".join(conditions)

    cur.execute(f"""
        SELECT e.id, e.title, e.event_date, e.end_date,
               et.name AS event_type, e.event_type_id,
               e.notes, e.fuzzy_date, e.latitude, e.longitude,
               e.place_id, e.place_label, e.trip_id,
               t.title AS trip_title,
               e.start_time, e.end_time, e.all_day,
               e.source, e.calendar_account, e.calendar_name
        FROM event e
        JOIN event_type et ON et.id = e.event_type_id
        LEFT JOIN trip t ON t.id = e.trip_id
        {where}
        ORDER BY e.event_date DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    cols = [desc[0] for desc in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(f"""
        SELECT count(*) FROM event e
        JOIN event_type et ON et.id = e.event_type_id
        {where}
    """, params)
    total = cur.fetchone()[0]

    cur.execute("SELECT EXTRACT(YEAR FROM event_date)::int AS y, count(*) FROM event WHERE deleted_at IS NULL GROUP BY y ORDER BY y DESC")
    years = [{"year": r[0], "count": r[1]} for r in cur.fetchall()]

    cur.execute("""
        SELECT et.name, count(*) FROM event e
        JOIN event_type et ON et.id = e.event_type_id
        WHERE e.deleted_at IS NULL
        GROUP BY et.name ORDER BY count(*) DESC
    """)
    types = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]

    return {"items": items, "total": total, "years": years, "types": types}


@router.post("/events", status_code=201)
def create_event(
    body: EventCreate,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    event_type_id = _resolve_event_type_id(cur, body.event_type)

    # Resolve place from mylocation if provided
    place_id = body.place_id
    place_label = None
    lat = body.latitude
    lon = body.longitude
    if place_id is not None:
        place = _resolve_place(place_id)
        if not place:
            raise HTTPException(400, f"Place {place_id} not found")
        place_label = place["name"]
        if lat is None:
            lat = place["lat"]
        if lon is None:
            lon = place["lon"]

    cur.execute("""
        INSERT INTO event (title, event_date, end_date, event_type_id, notes,
                           fuzzy_date, latitude, longitude, place_id, place_label, trip_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        body.title, body.event_date, body.end_date, event_type_id,
        body.notes, body.fuzzy_date, lat, lon,
        place_id, place_label, body.trip_id,
    ))
    event_id = cur.fetchone()[0]

    if body.documents:
        for doc in body.documents:
            cur.execute(
                "INSERT INTO event_document (event_id, paperless_id, label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (event_id, doc["paperless_id"], doc.get("label")),
            )

    conn.commit()
    return _fetch_event_detail(cur, event_id)


@router.get("/events/{event_id}")
def get_event(event_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    result = _fetch_event_detail(cur, event_id)
    if not result:
        raise HTTPException(404, "Event not found")
    return result


@router.put("/events/{event_id}")
def update_event(
    event_id: int,
    body: EventUpdate,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM event WHERE id = %s", (event_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Event not found")

    updates = []
    params = []
    for field in ("title", "event_date", "end_date", "notes"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.event_type is not None:
        event_type_id = _resolve_event_type_id(cur, body.event_type)
        updates.append("event_type_id = %s")
        params.append(event_type_id)
    if body.fuzzy_date is not None:
        updates.append("fuzzy_date = %s")
        params.append(body.fuzzy_date)
    if body.latitude is not None:
        updates.append("latitude = %s")
        params.append(body.latitude)
    if body.longitude is not None:
        updates.append("longitude = %s")
        params.append(body.longitude)
    # place_id: -1 = not provided, None = unlink, int = set
    if body.place_id != -1:
        if body.place_id is not None:
            place = _resolve_place(body.place_id)
            if not place:
                raise HTTPException(400, f"Place {body.place_id} not found")
            updates.append("place_id = %s")
            params.append(place["id"])
            updates.append("place_label = %s")
            params.append(place["name"])
        else:
            updates.append("place_id = %s")
            params.append(None)
            updates.append("place_label = %s")
            params.append(None)
    # trip_id: -1 = not provided, None = unlink, int = set
    if body.trip_id != -1:
        updates.append("trip_id = %s")
        params.append(body.trip_id)

    if not updates:
        return _fetch_event_detail(cur, event_id)

    updates.append("modified_at = now()")
    params.append(event_id)
    cur.execute(f"UPDATE event SET {', '.join(updates)} WHERE id = %s", params)
    conn.commit()
    return _fetch_event_detail(cur, event_id)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("DELETE FROM event WHERE id = %s", (event_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Event not found")
    conn.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Entry-event linking (used from entry detail enrichment panel)
# ---------------------------------------------------------------------------

class EventLink(BaseModel):
    event_id: int


@router.post("/entries/{entry_id}/events", status_code=201)
def link_event_to_entry(
    entry_id: int,
    body: EventLink,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")
    cur.execute(
        "INSERT INTO entry_event (entry_id, event_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (entry_id, body.event_id),
    )
    conn.commit()
    return {"linked": True}


@router.post("/entries/{entry_id}/events/all", status_code=201)
def link_all_events_to_entry(
    entry_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Link all events matching this entry's date."""
    cur = conn.cursor()
    cur.execute("SELECT created_at FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")
    entry_date = row[0].date() if hasattr(row[0], "date") else row[0]

    cur.execute("""
        INSERT INTO entry_event (entry_id, event_id)
        SELECT %s, id FROM event
        WHERE event_date <= %s AND COALESCE(end_date, event_date) >= %s
          AND deleted_at IS NULL
        ON CONFLICT DO NOTHING
    """, (entry_id, entry_date, entry_date))
    count = cur.rowcount
    conn.commit()
    return {"linked": count}


@router.delete("/entries/{entry_id}/events/{event_id}")
def unlink_event_from_entry(
    entry_id: int,
    event_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM entry_event WHERE entry_id = %s AND event_id = %s",
        (entry_id, event_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Event link not found")
    conn.commit()
    return {"unlinked": True}


# ---------------------------------------------------------------------------
# Document linking
# ---------------------------------------------------------------------------

@router.post("/events/{event_id}/documents", status_code=201)
def link_document(
    event_id: int,
    body: DocumentLink,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM event WHERE id = %s", (event_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Event not found")

    cur.execute(
        "INSERT INTO event_document (event_id, paperless_id, label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (event_id, body.paperless_id, body.label),
    )
    conn.commit()
    return {"linked": True}


@router.delete("/events/{event_id}/documents/{paperless_id}")
def unlink_document(
    event_id: int,
    paperless_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM event_document WHERE event_id = %s AND paperless_id = %s",
        (event_id, paperless_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Document link not found")
    conn.commit()
    return {"unlinked": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_event_detail(cur, event_id: int) -> dict | None:
    cur.execute("""
        SELECT e.id, e.title, e.event_date, e.end_date,
               et.name AS event_type, e.event_type_id,
               e.notes, e.fuzzy_date, e.latitude, e.longitude,
               e.place_id, e.place_label, e.trip_id,
               t.title AS trip_title,
               e.created_at, e.modified_at,
               e.start_time, e.end_time, e.all_day,
               e.source, e.calendar_account, e.calendar_name
        FROM event e
        JOIN event_type et ON et.id = e.event_type_id
        LEFT JOIN trip t ON t.id = e.trip_id
        WHERE e.id = %s AND e.deleted_at IS NULL
    """, (event_id,))
    row = cur.fetchone()
    if not row:
        return None

    cols = [desc[0] for desc in cur.description]
    event = dict(zip(cols, row))

    cur.execute(
        "SELECT paperless_id, label FROM event_document WHERE event_id = %s ORDER BY paperless_id",
        (event_id,),
    )
    event["documents"] = [{"paperless_id": r[0], "label": r[1]} for r in cur.fetchall()]

    return event
