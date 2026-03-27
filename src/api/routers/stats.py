from fastapi import APIRouter, Depends

from src.api.deps import get_conn, get_current_user
from src.api.models import StatsOut, TagOut

router = APIRouter()


@router.get("/stats", response_model=StatsOut)
def get_stats(conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM entry")
    total_entries = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM attachment WHERE type IN ('jpeg','png')")
    total_photos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM attachment WHERE type IN ('mov','mp4')")
    total_videos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tag")
    total_tags = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM journal WHERE is_trash = false")
    total_journals = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM location")
    entries_with_location = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM weather")
    entries_with_weather = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM music")
    entries_with_music = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM entry WHERE starred = true")
    starred_entries = cur.fetchone()[0]

    cur.execute("SELECT MIN(created_at), MAX(created_at) FROM entry")
    date_row = cur.fetchone()

    cur.execute("""
        SELECT gregorian_year, COUNT(*)
        FROM entry
        WHERE gregorian_year IS NOT NULL
        GROUP BY gregorian_year
        ORDER BY gregorian_year
    """)
    entries_by_year = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute("""
        SELECT t.id, t.name, COUNT(et.entry_id) as cnt
        FROM tag t
        JOIN entry_tag et ON et.tag_id = t.id
        GROUP BY t.id
        ORDER BY cnt DESC
        LIMIT 20
    """)
    top_tags = [TagOut(id=r[0], name=r[1], entry_count=r[2]) for r in cur.fetchall()]

    cur.execute("""
        SELECT l.country, l.locality, COUNT(*) as cnt
        FROM location l
        WHERE l.locality IS NOT NULL
        GROUP BY l.country, l.locality
        ORDER BY cnt DESC
        LIMIT 20
    """)
    top_locations = [
        {"country": r[0], "locality": r[1], "count": r[2]}
        for r in cur.fetchall()
    ]

    return StatsOut(
        total_entries=total_entries,
        total_photos=total_photos,
        total_videos=total_videos,
        total_tags=total_tags,
        total_journals=total_journals,
        entries_with_location=entries_with_location,
        entries_with_weather=entries_with_weather,
        entries_with_music=entries_with_music,
        starred_entries=starred_entries,
        date_range_start=date_row[0] if date_row else None,
        date_range_end=date_row[1] if date_row else None,
        entries_by_year=entries_by_year,
        top_tags=top_tags,
        top_locations=top_locations,
    )
