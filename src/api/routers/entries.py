import json

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_conn, get_current_user
from src.api.models import (
    AttachmentOut,
    EntryDetail,
    EntryList,
    EntrySummary,
    LocationOut,
    MusicOut,
    WeatherOut,
)

router = APIRouter()


def _build_summary(row, conn) -> EntrySummary:
    entry_id = row[0]
    text = row[6] or ""
    preview = text[:200].replace("\n", " ").strip() if text else None

    # Tags
    cur2 = conn.cursor()
    cur2.execute(
        "SELECT t.name FROM entry_tag et JOIN tag t ON t.id = et.tag_id WHERE et.entry_id = %s",
        (entry_id,),
    )
    tags = [r[0] for r in cur2.fetchall()]

    # Attachment count + first thumbnail
    cur2.execute(
        "SELECT COUNT(*), MIN(CASE WHEN type IN ('jpeg','png') THEN id END) FROM attachment WHERE entry_id = %s",
        (entry_id,),
    )
    att_row = cur2.fetchone()
    att_count = att_row[0] if att_row else 0
    thumb_id = att_row[1] if att_row else None
    thumb_url = f"/api/v1/media/{thumb_id}?thumb=1" if thumb_id else None

    # Location
    loc = None
    if row[8]:
        loc = LocationOut(
            latitude=row[8], longitude=row[9],
            place_name=row[10], locality=row[11],
            admin_area=row[12], country=row[13],
        )

    # Weather
    weather = None
    if row[14] is not None:
        weather = WeatherOut(temp_celsius=row[14], conditions=row[15], weather_code=row[16])

    # Music
    music = None
    if row[17]:
        music = MusicOut(track=row[17], artist=row[18], album=row[19])

    return EntrySummary(
        id=entry_id,
        uuid=row[1],
        journal_id=row[2],
        journal_name=row[3],
        created_at=row[4],
        starred=row[5],
        pinned=row[7],
        text_preview=preview,
        location=loc,
        weather=weather,
        music=music,
        tags=tags,
        attachment_count=att_count,
        thumbnail_url=thumb_url,
    )


@router.get("/entries", response_model=EntryList)
def list_entries(
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    journal_id: int | None = Query(None),
    tag: str | None = Query(None),
    starred: bool | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None),
    search: str | None = Query(None),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = []
    params: dict = {"limit": limit + 1}

    if cursor:
        conditions.append("e.created_at < %(cursor)s")
        params["cursor"] = cursor
    if journal_id:
        conditions.append("e.journal_id = %(journal_id)s")
        params["journal_id"] = journal_id
    if tag:
        conditions.append("EXISTS (SELECT 1 FROM entry_tag et JOIN tag t ON t.id = et.tag_id WHERE et.entry_id = e.id AND t.name = %(tag)s)")
        params["tag"] = tag
    if starred is not None:
        conditions.append("e.starred = %(starred)s")
        params["starred"] = starred
    if year:
        conditions.append("e.gregorian_year = %(year)s")
        params["year"] = year
    if month:
        conditions.append("e.gregorian_month = %(month)s")
        params["month"] = month
    if search:
        conditions.append("e.search_vector @@ plainto_tsquery('english', %(search)s)")
        params["search"] = search

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    cur.execute(f"""
        SELECT e.id, e.uuid, e.journal_id, j.name,
               e.created_at, e.starred, e.markdown_text, e.pinned,
               l.latitude, l.longitude, l.place_name, l.locality,
               l.admin_area, l.country,
               w.temp_celsius, w.conditions, w.weather_code,
               m.track, m.artist, m.album
        FROM entry e
        LEFT JOIN journal j ON j.id = e.journal_id
        LEFT JOIN location l ON l.entry_id = e.id
        LEFT JOIN weather w ON w.entry_id = e.id
        LEFT JOIN music m ON m.entry_id = e.id
        {where}
        ORDER BY e.created_at DESC
        LIMIT %(limit)s
    """, params)

    rows = cur.fetchall()
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = [_build_summary(r, conn) for r in rows]
    next_cursor = items[-1].created_at.isoformat() if items and has_more else None

    # Total count (only on first page)
    total = None
    if not cursor:
        params_count = {k: v for k, v in params.items() if k != "limit"}
        where_count = where
        cur.execute(f"SELECT COUNT(*) FROM entry e {where_count}", params_count)
        total = cur.fetchone()[0]

    return EntryList(items=items, next_cursor=next_cursor, has_more=has_more, total=total)


@router.get("/entries/{entry_id}", response_model=EntryDetail)
def get_entry(entry_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.uuid, e.journal_id, j.name,
               e.created_at, e.modified_at, e.markdown_text, e.rich_text_json,
               e.starred, e.pinned, e.is_draft, e.is_all_day, e.duration,
               e.device_name, e.device_model, e.timezone
        FROM entry e
        LEFT JOIN journal j ON j.id = e.journal_id
        WHERE e.id = %s
    """, (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")

    # Location
    cur.execute("SELECT latitude, longitude, altitude, place_name, address, locality, admin_area, country FROM location WHERE entry_id = %s", (entry_id,))
    loc_row = cur.fetchone()
    loc = LocationOut(latitude=loc_row[0], longitude=loc_row[1], altitude=loc_row[2], place_name=loc_row[3], address=loc_row[4], locality=loc_row[5], admin_area=loc_row[6], country=loc_row[7]) if loc_row else None

    # Weather
    cur.execute("SELECT temp_celsius, conditions, weather_code, relative_humidity, wind_speed_kph, pressure_mb, visibility_km, moon_phase, sunrise, sunset FROM weather WHERE entry_id = %s", (entry_id,))
    w_row = cur.fetchone()
    weather = WeatherOut(temp_celsius=w_row[0], conditions=w_row[1], weather_code=w_row[2], relative_humidity=w_row[3], wind_speed_kph=w_row[4], pressure_mb=w_row[5], visibility_km=w_row[6], moon_phase=w_row[7], sunrise=w_row[8], sunset=w_row[9]) if w_row else None

    # Music
    cur.execute("SELECT track, artist, album, album_year FROM music WHERE entry_id = %s", (entry_id,))
    m_row = cur.fetchone()
    music = MusicOut(track=m_row[0], artist=m_row[1], album=m_row[2], album_year=m_row[3]) if m_row else None

    # Tags
    cur.execute("SELECT t.name FROM entry_tag et JOIN tag t ON t.id = et.tag_id WHERE et.entry_id = %s", (entry_id,))
    tags = [r[0] for r in cur.fetchall()]

    # Attachments
    cur.execute("""
        SELECT id, uuid, type, filename, width, height, caption, duration,
               is_favorite, camera_make, camera_model, date
        FROM attachment WHERE entry_id = %s ORDER BY order_in_entry, id
    """, (entry_id,))
    attachments = [
        AttachmentOut(
            id=a[0], uuid=a[1], type=a[2], filename=a[3],
            width=a[4], height=a[5], caption=a[6], duration=a[7],
            is_favorite=a[8], camera_make=a[9], camera_model=a[10],
            date=a[11], media_url=f"/api/v1/media/{a[0]}",
        )
        for a in cur.fetchall()
    ]

    rich_text = None
    if row[7]:
        try:
            rich_text = json.loads(row[7]) if isinstance(row[7], str) else row[7]
        except (json.JSONDecodeError, TypeError):
            pass

    return EntryDetail(
        id=row[0], uuid=row[1], journal_id=row[2], journal_name=row[3],
        created_at=row[4], modified_at=row[5],
        markdown_text=row[6], rich_text_json=rich_text,
        starred=row[8], pinned=row[9], is_draft=row[10],
        is_all_day=row[11], duration=row[12],
        device_name=row[13], device_model=row[14], timezone=row[15],
        location=loc, weather=weather, music=music,
        tags=tags, attachments=attachments,
    )


@router.put("/entries/{entry_id}/star")
def toggle_star(entry_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("UPDATE entry SET starred = NOT starred WHERE id = %s RETURNING starred", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")
    conn.commit()
    return {"starred": row[0]}
