from fastapi import APIRouter, Depends, Query

from src.api.deps import get_conn, get_current_user
from src.api.models import EntryList, EntrySummary, LocationOut, MusicOut, WeatherOut

router = APIRouter()


@router.get("/search", response_model=EntryList)
def search_entries(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.uuid, e.journal_id, j.name,
               e.created_at, e.starred, e.markdown_text, e.pinned,
               l.latitude, l.longitude, l.place_name, l.locality,
               l.admin_area, l.country,
               w.temp_celsius, w.conditions, w.weather_code,
               m.track, m.artist, m.album,
               ts_rank(e.search_vector, query) as rank
        FROM entry e
        CROSS JOIN plainto_tsquery('english', %(q)s) query
        LEFT JOIN journal j ON j.id = e.journal_id
        LEFT JOIN LATERAL (
            SELECT * FROM location WHERE entry_id = e.id
            ORDER BY CASE WHEN location_type = 'primary' THEN 0 ELSE 1 END, sequence_order
            LIMIT 1
        ) l ON true
        LEFT JOIN weather w ON w.entry_id = e.id
        LEFT JOIN LATERAL (
            SELECT * FROM music WHERE entry_id = e.id
            ORDER BY CASE WHEN source = 'dayone' THEN 0 ELSE 1 END, played_at DESC NULLS LAST
            LIMIT 1
        ) m ON true
        WHERE e.search_vector @@ query
        ORDER BY rank DESC, e.created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, {"q": q, "limit": limit + 1, "offset": offset})

    rows = cur.fetchall()
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = []
    for r in rows:
        text = r[6] or ""
        preview = text[:200].replace("\n", " ").strip() if text else None

        # Attachment count + thumbnail
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT COUNT(*), MIN(CASE WHEN type IN ('jpeg','png') THEN id END) FROM attachment WHERE entry_id = %s",
            (r[0],),
        )
        att_row = cur2.fetchone()

        # Tags
        cur2.execute("SELECT t.name FROM entry_tag et JOIN tag t ON t.id = et.tag_id WHERE et.entry_id = %s", (r[0],))
        tags = [t[0] for t in cur2.fetchall()]

        loc = LocationOut(latitude=r[8], longitude=r[9], place_name=r[10], locality=r[11], admin_area=r[12], country=r[13]) if r[8] else None
        weather = WeatherOut(temp_celsius=r[14], conditions=r[15], weather_code=r[16]) if r[14] is not None else None
        music = MusicOut(track=r[17], artist=r[18], album=r[19]) if r[17] else None
        thumb_id = att_row[1] if att_row else None

        items.append(EntrySummary(
            id=r[0], uuid=r[1], journal_id=r[2], journal_name=r[3],
            created_at=r[4], starred=r[5], pinned=r[7],
            text_preview=preview, location=loc, weather=weather, music=music,
            tags=tags, attachment_count=att_row[0] if att_row else 0,
            thumbnail_url=f"/api/v1/media/{thumb_id}?thumb=1" if thumb_id else None,
        ))

    # Total
    cur.execute("SELECT COUNT(*) FROM entry e CROSS JOIN plainto_tsquery('english', %(q)s) query WHERE e.search_vector @@ query", {"q": q})
    total = cur.fetchone()[0]

    return EntryList(items=items, has_more=has_more, total=total)
