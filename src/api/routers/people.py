"""Person management — CRUD for people and entry-person links."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


class PersonCreate(BaseModel):
    name: str
    nickname: str | None = None
    notes: str | None = None


class PersonUpdate(BaseModel):
    name: str | None = None
    nickname: str | None = None
    notes: str | None = None


class EntryPersonLink(BaseModel):
    person_id: int
    role: str | None = None  # 'companion', 'host', 'met', etc.


@router.get("/people")
def list_people(
    q: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    if q:
        cur.execute("""
            SELECT p.id, p.name, p.nickname, p.notes, p.immich_person_id,
                   (SELECT count(*) FROM entry_person ep WHERE ep.person_id = p.id) AS entry_count
            FROM person p
            WHERE p.name ILIKE %s OR p.nickname ILIKE %s
            ORDER BY p.name
            LIMIT %s
        """, (f"%{q}%", f"%{q}%", limit))
    else:
        cur.execute("""
            SELECT p.id, p.name, p.nickname, p.notes, p.immich_person_id,
                   (SELECT count(*) FROM entry_person ep WHERE ep.person_id = p.id) AS entry_count
            FROM person p
            ORDER BY p.name
            LIMIT %s
        """, (limit,))

    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@router.post("/people", status_code=201)
def create_person(body: PersonCreate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO person (name, nickname, notes)
           VALUES (%s, %s, %s)
           ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
           RETURNING id""",
        (body.name, body.nickname, body.notes),
    )
    person_id = cur.fetchone()[0]
    conn.commit()
    return {"id": person_id, "name": body.name}


@router.put("/people/{person_id}")
def update_person(person_id: int, body: PersonUpdate, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("SELECT id FROM person WHERE id = %s", (person_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Person not found")

    updates = []
    params = []
    for field in ("name", "nickname", "notes"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if not updates:
        return {"updated": False}

    params.append(person_id)
    cur.execute(f"UPDATE person SET {', '.join(updates)} WHERE id = %s", params)
    conn.commit()
    return {"updated": True}


@router.get("/entries/{entry_id}/people")
def get_entry_people(entry_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.nickname, ep.role
        FROM entry_person ep
        JOIN person p ON p.id = ep.person_id
        WHERE ep.entry_id = %s
        ORDER BY p.name
    """, (entry_id,))
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@router.post("/entries/{entry_id}/people", status_code=201)
def link_person(entry_id: int, body: EntryPersonLink, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    cur.execute(
        """INSERT INTO entry_person (entry_id, person_id, role)
           VALUES (%s, %s, %s)
           ON CONFLICT (entry_id, person_id) DO UPDATE SET role = EXCLUDED.role""",
        (entry_id, body.person_id, body.role),
    )
    conn.commit()
    return {"linked": True}


@router.delete("/entries/{entry_id}/people/{person_id}")
def unlink_person(entry_id: int, person_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM entry_person WHERE entry_id = %s AND person_id = %s",
        (entry_id, person_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Link not found")
    conn.commit()
    return {"unlinked": True}
