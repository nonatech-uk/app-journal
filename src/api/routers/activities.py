"""Activity linking — CRUD for activity records (skiing days etc.)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


class SkiingDayLink(BaseModel):
    skiing_day_id: int
    location: str | None = None


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
