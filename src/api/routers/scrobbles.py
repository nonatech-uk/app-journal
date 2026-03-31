"""Scrobble import — link scrobbles from the scrobble DB into the music table."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


class ScrobbleImport(BaseModel):
    scrobble_ids: list[int]


@router.post("/entries/{entry_id}/import-scrobbles")
def import_scrobbles(
    entry_id: int,
    body: ScrobbleImport,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    from config.settings import settings
    from src.api.routers.enrichment import _safe_query

    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    if not settings.scrobble_db_password:
        raise HTTPException(503, "Scrobble database not configured")

    if not body.scrobble_ids:
        return {"imported": 0}

    # Fetch scrobble details from external DB
    scrobble_dsn = settings.cross_dsn(settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password)
    placeholders = ",".join(["%s"] * len(body.scrobble_ids))
    rows = _safe_query(
        scrobble_dsn,
        f"""SELECT s.id, ar.name AS artist, t.title AS track,
                   t.album_title AS album, s.listened_at
            FROM scrobble s
            JOIN track t ON t.id = s.track_id
            JOIN track_artist ta ON ta.track_id = t.id
            JOIN artist ar ON ar.id = ta.artist_id
            WHERE s.id IN ({placeholders})
            ORDER BY s.listened_at""",
        tuple(body.scrobble_ids),
    )

    imported = 0
    for row in rows:
        cur.execute(
            """INSERT INTO music (entry_id, track, artist, album, played_at, source, scrobble_db_id)
               VALUES (%s, %s, %s, %s, %s, 'scrobble', %s)
               ON CONFLICT (entry_id, scrobble_db_id) WHERE scrobble_db_id IS NOT NULL
               DO NOTHING""",
            (entry_id, row["track"], row["artist"], row["album"], row["listened_at"], row["id"]),
        )
        imported += cur.rowcount

    # Backfill MBIDs from enrichment link table
    from src.services.daily_summary import _backfill_mbids
    _backfill_mbids(conn, scrobble_dsn, entry_id)

    conn.commit()
    return {"imported": imported}


@router.post("/entries/{entry_id}/import-all-scrobbles")
def import_all_scrobbles(
    entry_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Import all scrobbles from the ±2 hour window around the entry."""
    from datetime import timedelta

    from config.settings import settings
    from src.api.routers.enrichment import _safe_query

    cur = conn.cursor()
    cur.execute("SELECT created_at FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")

    if not settings.scrobble_db_password:
        raise HTTPException(503, "Scrobble database not configured")

    entry_date = row[0]
    window_start = entry_date - timedelta(hours=2)
    window_end = entry_date + timedelta(hours=2)

    scrobble_dsn = settings.cross_dsn(settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password)
    rows = _safe_query(
        scrobble_dsn,
        """SELECT s.id, ar.name AS artist, t.title AS track,
                  t.album_title AS album, s.listened_at
           FROM scrobble s
           JOIN track t ON t.id = s.track_id
           JOIN track_artist ta ON ta.track_id = t.id
           JOIN artist ar ON ar.id = ta.artist_id
           WHERE s.listened_at BETWEEN %s AND %s
           ORDER BY s.listened_at""",
        (window_start, window_end),
    )

    imported = 0
    for row in rows:
        cur.execute(
            """INSERT INTO music (entry_id, track, artist, album, played_at, source, scrobble_db_id)
               VALUES (%s, %s, %s, %s, %s, 'scrobble', %s)
               ON CONFLICT (entry_id, scrobble_db_id) WHERE scrobble_db_id IS NOT NULL
               DO NOTHING""",
            (entry_id, row["track"], row["artist"], row["album"], row["listened_at"], row["id"]),
        )
        imported += cur.rowcount

    # Backfill MBIDs from enrichment link table
    from src.services.daily_summary import _backfill_mbids
    _backfill_mbids(conn, scrobble_dsn, entry_id)

    conn.commit()
    return {"imported": imported, "total_in_window": len(rows)}
