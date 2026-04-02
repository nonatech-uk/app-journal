from datetime import date

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_conn, get_current_user
from src.api.models import CalendarDay, CalendarMonth, EntrySummary, LocationOut, MusicOut, OnThisDayEntry, WeatherOut

router = APIRouter()


@router.get("/calendar", response_model=list[CalendarMonth])
def calendar_months(conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT gregorian_year, gregorian_month,
               COUNT(*) as cnt,
               array_agg(DISTINCT gregorian_day) as days
        FROM entry
        WHERE gregorian_year IS NOT NULL
        GROUP BY gregorian_year, gregorian_month
        ORDER BY gregorian_year DESC, gregorian_month DESC
    """)
    months = [
        CalendarMonth(year=r[0], month=r[1], entry_count=r[2], days=sorted(r[3]))
        for r in cur.fetchall()
    ]

    # For each day, find the best entry to link to:
    # prefer daily_summary, otherwise the earliest diary entry
    cur.execute("""
        SELECT DISTINCT ON (gregorian_year, gregorian_month, gregorian_day)
               gregorian_year, gregorian_month, gregorian_day, id
        FROM entry
        WHERE gregorian_year IS NOT NULL
        ORDER BY gregorian_year, gregorian_month, gregorian_day,
                 CASE WHEN entry_type = 'daily_summary' THEN 0 ELSE 1 END,
                 created_at
    """)
    day_entry_map: dict[tuple[int, int, int], int] = {}
    for r in cur.fetchall():
        day_entry_map[(r[0], r[1], r[2])] = r[3]

    for m in months:
        m.day_entries = [
            CalendarDay(day=d, entry_id=day_entry_map[(m.year, m.month, d)])
            for d in m.days
            if (m.year, m.month, d) in day_entry_map
        ]

    return months


@router.get("/on-this-day", response_model=list[OnThisDayEntry])
def on_this_day(
    month: int = Query(None),
    day: int = Query(None),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    today = date.today()
    m = month or today.month
    d = day or today.day

    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.uuid, e.journal_id, j.name,
               e.created_at, e.starred, e.markdown_text, e.pinned,
               e.gregorian_year,
               l.latitude, l.longitude, l.place_name, l.locality,
               l.admin_area, l.country,
               w.temp_celsius, w.conditions, w.weather_code,
               m.track, m.artist, m.album
        FROM entry e
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
        WHERE e.gregorian_month = %s AND e.gregorian_day = %s
              AND e.parent_entry_id IS NULL
        ORDER BY e.created_at DESC
    """, (m, d))

    import random
    all_rows = cur.fetchall()
    if len(all_rows) > 3:
        all_rows = sorted(random.sample(all_rows, 3), key=lambda r: r[4], reverse=True)

    results = []
    for r in all_rows:
        text = r[6] or ""
        preview = text[:200].replace("\n", " ").strip() if text else None

        cur2 = conn.cursor()
        cur2.execute(
            "SELECT COUNT(*), MIN(CASE WHEN type IN ('jpeg','png') THEN id END) FROM attachment WHERE entry_id = %s",
            (r[0],),
        )
        att_row = cur2.fetchone()
        cur2.execute("SELECT t.name FROM entry_tag et JOIN tag t ON t.id = et.tag_id WHERE et.entry_id = %s", (r[0],))
        tags = [t[0] for t in cur2.fetchall()]

        loc = LocationOut(latitude=r[9], longitude=r[10], place_name=r[11], locality=r[12], admin_area=r[13], country=r[14]) if r[9] else None
        weather = WeatherOut(temp_celsius=r[15], conditions=r[16], weather_code=r[17]) if r[15] is not None else None
        music = MusicOut(track=r[18], artist=r[19], album=r[20]) if r[18] else None
        thumb_id = att_row[1] if att_row else None

        summary = EntrySummary(
            id=r[0], uuid=r[1], journal_id=r[2], journal_name=r[3],
            created_at=r[4], starred=r[5], pinned=r[7],
            text_preview=preview, location=loc, weather=weather, music=music,
            tags=tags, attachment_count=att_row[0] if att_row else 0,
            thumbnail_url=f"/api/v1/media/{thumb_id}?thumb=1" if thumb_id else None,
        )
        results.append(OnThisDayEntry(year=r[8], entry=summary))

    return results
