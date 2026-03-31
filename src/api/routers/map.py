from fastapi import APIRouter, Depends, Query

from src.api.deps import get_conn, get_current_user
from src.api.models import MapEntry

router = APIRouter()


@router.get("/map/entries", response_model=list[MapEntry])
def map_entries(
    year: int | None = Query(None),
    journal_id: int | None = Query(None),
    limit: int = Query(5000, ge=1, le=10000),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = ["l.latitude IS NOT NULL"]
    params: dict = {"limit": limit}

    if year:
        conditions.append("e.gregorian_year = %(year)s")
        params["year"] = year
    if journal_id:
        conditions.append("e.journal_id = %(journal_id)s")
        params["journal_id"] = journal_id

    where = "WHERE " + " AND ".join(conditions)

    cur.execute(f"""
        SELECT e.id, e.uuid, e.created_at, e.markdown_text,
               l.latitude, l.longitude, l.place_name,
               (SELECT MIN(a.id) FROM attachment a WHERE a.entry_id = e.id AND a.type IN ('jpeg','png')) as thumb_att_id
        FROM entry e
        JOIN LATERAL (
            SELECT * FROM location WHERE entry_id = e.id
            ORDER BY CASE WHEN location_type = 'primary' THEN 0 ELSE 1 END, sequence_order
            LIMIT 1
        ) l ON true
        {where}
        ORDER BY e.created_at DESC
        LIMIT %(limit)s
    """, params)

    return [
        MapEntry(
            id=r[0], uuid=r[1], created_at=r[2],
            text_preview=(r[3] or "")[:100].replace("\n", " ").strip() or None,
            latitude=r[4], longitude=r[5], place_name=r[6],
            thumbnail_url=f"/api/v1/media/{r[7]}?thumb=1" if r[7] else None,
        )
        for r in cur.fetchall()
    ]
