"""Flight linking — CRUD for entry_flight associations."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


class FlightLink(BaseModel):
    flight_id: int
    flight_type: str = "commercial"  # 'commercial' | 'ga'


@router.get("/entries/{entry_id}/flights")
def get_entry_flights(entry_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    cur.execute(
        "SELECT flight_id, flight_type FROM entry_flight WHERE entry_id = %s",
        (entry_id,),
    )
    return [{"flight_id": r[0], "flight_type": r[1]} for r in cur.fetchall()]


@router.post("/entries/{entry_id}/flights", status_code=201)
def link_flight(
    entry_id: int,
    body: FlightLink,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    cur.execute(
        """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
           VALUES (%s, %s, %s)
           ON CONFLICT DO NOTHING""",
        (entry_id, body.flight_id, body.flight_type),
    )
    conn.commit()
    return {"linked": True}


@router.delete("/entries/{entry_id}/flights/{flight_id}")
def unlink_flight(
    entry_id: int,
    flight_id: int,
    flight_type: str = "commercial",
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM entry_flight WHERE entry_id = %s AND flight_id = %s AND flight_type = %s",
        (entry_id, flight_id, flight_type),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Flight link not found")
    conn.commit()
    return {"unlinked": True}
