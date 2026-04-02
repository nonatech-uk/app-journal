"""Activity CRUD — activity types, standalone activities, entry linking, and ingest."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from config.settings import settings
from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SkiingDayLink(BaseModel):
    skiing_day_id: int
    location: str | None = None


class ActivityTypeCreate(BaseModel):
    name: str


class ActivityTypeUpdate(BaseModel):
    name: str


class ActivityCreate(BaseModel):
    title: str
    activity_type: str
    date: str
    start_time: str | None = None
    distance_km: float | None = None
    duration_seconds: int | None = None
    moving_time_seconds: int | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    max_altitude: float | None = None
    avg_speed_kmh: float | None = None
    max_speed_kmh: float | None = None
    avg_heartrate: float | None = None
    max_heartrate: float | None = None
    calories: float | None = None
    conditions: str | None = None
    notes: str | None = None


class ActivityUpdate(BaseModel):
    title: str | None = None
    activity_type: str | None = None
    date: str | None = None
    start_time: str | None = None
    distance_km: float | None = None
    duration_seconds: int | None = None
    moving_time_seconds: int | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    max_altitude: float | None = None
    avg_speed_kmh: float | None = None
    max_speed_kmh: float | None = None
    avg_heartrate: float | None = None
    max_heartrate: float | None = None
    calories: float | None = None
    conditions: str | None = None
    notes: str | None = None


class ActivityIngestItem(BaseModel):
    strava_activity_id: int
    title: str
    activity_type: str
    date: str
    start_time: str | None = None
    distance_km: float | None = None
    duration_seconds: int | None = None
    moving_time_seconds: int | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    max_altitude: float | None = None
    avg_speed_kmh: float | None = None
    max_speed_kmh: float | None = None
    avg_heartrate: float | None = None
    max_heartrate: float | None = None
    calories: float | None = None


class ActivityIngest(BaseModel):
    activities: list[ActivityIngestItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_pipeline_auth(authorization: str = Header(...)):
    if not settings.pipeline_secret:
        raise HTTPException(503, "Ingest endpoint not configured")
    if not authorization.startswith("Bearer "):
        raise HTTPException(403, "Invalid credentials")
    if not secrets.compare_digest(authorization[7:], settings.pipeline_secret):
        raise HTTPException(403, "Invalid credentials")


def _resolve_activity_type_id(cur, name: str) -> int:
    """Resolve activity type name to ID, creating if missing."""
    name = name.strip().lower()
    cur.execute("SELECT id FROM activity_type WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO activity_type (name) VALUES (%s) RETURNING id", (name,))
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Activity Type CRUD
# ---------------------------------------------------------------------------

@router.get("/activity-types")
def list_activity_types(conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT at.id, at.name, count(a.id) AS activity_count
        FROM activity_type at
        LEFT JOIN activity a ON a.activity_type = at.name
        GROUP BY at.id, at.name
        ORDER BY at.name
    """)
    return [{"id": r[0], "name": r[1], "activity_count": r[2]} for r in cur.fetchall()]


@router.post("/activity-types", status_code=201)
def create_activity_type(body: ActivityTypeCreate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    name = body.name.strip().lower()
    if not name:
        raise HTTPException(400, "Activity type name cannot be empty")
    cur.execute("SELECT id FROM activity_type WHERE name = %s", (name,))
    if cur.fetchone():
        raise HTTPException(409, f"Activity type '{name}' already exists")
    cur.execute("INSERT INTO activity_type (name) VALUES (%s) RETURNING id", (name,))
    type_id = cur.fetchone()[0]
    conn.commit()
    return {"id": type_id, "name": name, "activity_count": 0}


@router.put("/activity-types/{type_id}")
def update_activity_type(type_id: int, body: ActivityTypeUpdate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    name = body.name.strip().lower()
    if not name:
        raise HTTPException(400, "Activity type name cannot be empty")
    cur.execute("SELECT id FROM activity_type WHERE name = %s AND id != %s", (name, type_id))
    if cur.fetchone():
        raise HTTPException(409, f"Activity type '{name}' already exists")
    cur.execute("UPDATE activity_type SET name = %s WHERE id = %s", (name, type_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Activity type not found")
    conn.commit()
    return {"id": type_id, "name": name}


@router.delete("/activity-types/{type_id}")
def delete_activity_type(type_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM activity WHERE activity_type = (SELECT name FROM activity_type WHERE id = %s)", (type_id,))
    count = cur.fetchone()[0]
    if count > 0:
        raise HTTPException(409, f"Cannot delete: {count} activities still use this type")
    cur.execute("DELETE FROM activity_type WHERE id = %s", (type_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Activity type not found")
    conn.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Standalone Activity CRUD
# ---------------------------------------------------------------------------

_ACTIVITY_COLS = """id, activity_type, title, date, start_time, distance_km,
    duration_seconds, moving_time_seconds, elevation_gain, elevation_loss,
    max_altitude, avg_speed_kmh, max_speed_kmh, avg_heartrate, max_heartrate,
    calories, conditions, notes, source, strava_activity_id, entry_id"""


@router.get("/activities")
def list_activities(
    year: int | None = Query(None),
    activity_type: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions: list[str] = []
    params: dict = {"limit": limit, "offset": offset}

    if year:
        conditions.append("EXTRACT(YEAR FROM date) = %(year)s")
        params["year"] = year
    if activity_type:
        conditions.append("activity_type = %(activity_type)s")
        params["activity_type"] = activity_type

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    cur.execute(f"""
        SELECT {_ACTIVITY_COLS}
        FROM activity
        {where}
        ORDER BY date DESC NULLS LAST, start_time NULLS LAST
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    cols = [desc[0] for desc in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(f"SELECT count(*) FROM activity {where}", params)
    total = cur.fetchone()[0]

    cur.execute("SELECT EXTRACT(YEAR FROM date)::int AS y, count(*) FROM activity WHERE date IS NOT NULL GROUP BY y ORDER BY y DESC")
    years = [{"year": r[0], "count": r[1]} for r in cur.fetchall()]

    cur.execute("SELECT activity_type, count(*) FROM activity GROUP BY activity_type ORDER BY activity_type")
    types = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]

    return {"items": items, "total": total, "years": years, "types": types}


@router.get("/activities/{activity_id}")
def get_activity(activity_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute(f"SELECT {_ACTIVITY_COLS} FROM activity WHERE id = %s", (activity_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Activity not found")
    cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


@router.post("/activities", status_code=201)
def create_activity(body: ActivityCreate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    type_id = _resolve_activity_type_id(cur, body.activity_type)
    cur.execute("""
        INSERT INTO activity (title, activity_type, activity_type_id, date, start_time,
            distance_km, duration_seconds, moving_time_seconds,
            elevation_gain, elevation_loss, max_altitude,
            avg_speed_kmh, max_speed_kmh, avg_heartrate, max_heartrate,
            calories, conditions, notes, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual')
        RETURNING id
    """, (body.title, body.activity_type.strip().lower(), type_id, body.date, body.start_time,
          body.distance_km, body.duration_seconds, body.moving_time_seconds,
          body.elevation_gain, body.elevation_loss, body.max_altitude,
          body.avg_speed_kmh, body.max_speed_kmh, body.avg_heartrate, body.max_heartrate,
          body.calories, body.conditions, body.notes))
    activity_id = cur.fetchone()[0]
    conn.commit()
    return {"id": activity_id}


@router.put("/activities/{activity_id}")
def update_activity(activity_id: int, body: ActivityUpdate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("SELECT source FROM activity WHERE id = %s", (activity_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Activity not found")

    updates = []
    params = []
    for field in ["title", "date", "start_time", "distance_km", "duration_seconds",
                  "moving_time_seconds", "elevation_gain", "elevation_loss", "max_altitude",
                  "avg_speed_kmh", "max_speed_kmh", "avg_heartrate", "max_heartrate",
                  "calories", "conditions", "notes"]:
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.activity_type is not None:
        type_name = body.activity_type.strip().lower()
        type_id = _resolve_activity_type_id(cur, type_name)
        updates.append("activity_type = %s")
        params.append(type_name)
        updates.append("activity_type_id = %s")
        params.append(type_id)

    if not updates:
        raise HTTPException(400, "No fields to update")
    params.append(activity_id)
    cur.execute(f"UPDATE activity SET {', '.join(updates)} WHERE id = %s", params)
    conn.commit()
    return {"updated": True}


@router.delete("/activities/{activity_id}")
def delete_standalone_activity(activity_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("SELECT source FROM activity WHERE id = %s", (activity_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Activity not found")
    cur.execute("DELETE FROM activity WHERE id = %s", (activity_id,))
    conn.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Activity ↔ Entry linking
# ---------------------------------------------------------------------------

@router.post("/entries/{entry_id}/activities/{activity_id}/link", status_code=200)
def link_activity_to_entry(
    entry_id: int,
    activity_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")
    cur.execute("SELECT id, entry_id FROM activity WHERE id = %s", (activity_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Activity not found")
    if row[1] == entry_id:
        return {"linked": True, "already_existed": True}
    cur.execute("UPDATE activity SET entry_id = %s WHERE id = %s", (entry_id, activity_id))
    conn.commit()
    return {"linked": True}


@router.delete("/entries/{entry_id}/activities/{activity_id}/link")
def unlink_activity_from_entry(
    entry_id: int,
    activity_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM activity WHERE id = %s AND entry_id = %s", (activity_id, entry_id))
    if not cur.fetchone():
        raise HTTPException(404, "Activity not linked to this entry")
    cur.execute("UPDATE activity SET entry_id = NULL WHERE id = %s", (activity_id,))
    conn.commit()
    return {"unlinked": True}


# ---------------------------------------------------------------------------
# Legacy entry-scoped endpoints (skiing days, entry activities)
# ---------------------------------------------------------------------------

@router.get("/entries/{entry_id}/activities")
def get_entry_activities(entry_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    cur.execute(
        """SELECT id, activity_type, title, skiing_day_id, distance_km,
                  duration_seconds, elevation_gain, elevation_loss,
                  max_altitude, conditions, notes
           FROM activity WHERE entry_id = %s ORDER BY id""",
        (entry_id,),
    )
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@router.post("/entries/{entry_id}/activities/skiing", status_code=201)
def link_skiing_day(
    entry_id: int,
    body: SkiingDayLink,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    # Check not already linked
    cur.execute(
        "SELECT id FROM activity WHERE entry_id = %s AND skiing_day_id = %s",
        (entry_id, body.skiing_day_id),
    )
    if cur.fetchone():
        return {"linked": True, "already_existed": True}

    cur.execute(
        """INSERT INTO activity (entry_id, activity_type, title, skiing_day_id)
           VALUES (%s, 'skiing', %s, %s)
           RETURNING id""",
        (entry_id, body.location or "Skiing", body.skiing_day_id),
    )
    activity_id = cur.fetchone()[0]
    conn.commit()
    return {"linked": True, "activity_id": activity_id}


@router.delete("/entries/{entry_id}/activities/{activity_id}")
def delete_activity(
    entry_id: int,
    activity_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM activity WHERE id = %s AND entry_id = %s",
        (activity_id, entry_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Activity not found")
    conn.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Strava ingest (from my-locations sync)
# ---------------------------------------------------------------------------

@router.post("/activities/ingest")
def ingest_activities(
    body: ActivityIngest,
    conn=Depends(get_conn),
    _=Depends(_check_pipeline_auth),
):
    """Ingest activities from Strava sync. Upserts by strava_activity_id."""
    cur = conn.cursor()
    created = 0
    updated = 0
    for item in body.activities:
        type_id = _resolve_activity_type_id(cur, item.activity_type)
        cur.execute("""
            INSERT INTO activity (strava_activity_id, title, activity_type, activity_type_id,
                date, start_time, distance_km, duration_seconds, moving_time_seconds,
                elevation_gain, elevation_loss, max_altitude,
                avg_speed_kmh, max_speed_kmh, avg_heartrate, max_heartrate,
                calories, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'strava')
            ON CONFLICT (strava_activity_id) DO UPDATE SET
                title = EXCLUDED.title,
                activity_type = EXCLUDED.activity_type,
                activity_type_id = EXCLUDED.activity_type_id,
                date = EXCLUDED.date,
                start_time = EXCLUDED.start_time,
                distance_km = EXCLUDED.distance_km,
                duration_seconds = EXCLUDED.duration_seconds,
                moving_time_seconds = EXCLUDED.moving_time_seconds,
                elevation_gain = EXCLUDED.elevation_gain,
                elevation_loss = EXCLUDED.elevation_loss,
                max_altitude = EXCLUDED.max_altitude,
                avg_speed_kmh = EXCLUDED.avg_speed_kmh,
                max_speed_kmh = EXCLUDED.max_speed_kmh,
                avg_heartrate = EXCLUDED.avg_heartrate,
                max_heartrate = EXCLUDED.max_heartrate,
                calories = EXCLUDED.calories
            RETURNING (xmax = 0) AS inserted
        """, (item.strava_activity_id, item.title, item.activity_type.strip().lower(), type_id,
              item.date, item.start_time, item.distance_km, item.duration_seconds,
              item.moving_time_seconds, item.elevation_gain, item.elevation_loss,
              item.max_altitude, item.avg_speed_kmh, item.max_speed_kmh,
              item.avg_heartrate, item.max_heartrate, item.calories))
        row = cur.fetchone()
        if row and row[0]:
            created += 1
        else:
            updated += 1
    conn.commit()
    return {"created": created, "updated": updated, "total": len(body.activities)}
