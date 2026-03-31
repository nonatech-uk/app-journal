"""Media watch import — persist Tautulli watches into media_watch table."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


class WatchImport(BaseModel):
    title: str
    media_type: str  # 'movie' | 'episode'
    series_title: str | None = None
    season: int | None = None
    episode: int | None = None
    platform: str | None = None
    year: int | None = None
    reference_id: int | str | None = None
    watched_at: int | None = None  # unix timestamp from Tautulli


@router.post("/entries/{entry_id}/import-watches")
def import_watches(
    entry_id: int,
    body: list[WatchImport],
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    imported = 0
    for w in body:
        watched_at = datetime.fromtimestamp(w.watched_at, tz=timezone.utc) if w.watched_at else None
        session_key = str(w.reference_id) if w.reference_id else None

        cur.execute(
            """INSERT INTO media_watch
                   (entry_id, title, media_type, series_title, season, episode,
                    platform, tautulli_session_key, watched_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (entry_id, tautulli_session_key)
                   WHERE tautulli_session_key IS NOT NULL
               DO NOTHING""",
            (entry_id, w.title, w.media_type, w.series_title, w.season, w.episode,
             w.platform, session_key, watched_at),
        )
        imported += cur.rowcount

    conn.commit()
    return {"imported": imported}


@router.post("/entries/{entry_id}/import-all-watches")
def import_all_watches(
    entry_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Import all movie/episode watches from Tautulli for the entry's date."""
    import httpx

    from config.settings import settings

    cur = conn.cursor()
    cur.execute("SELECT created_at FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")

    if not settings.tautulli_api_key:
        raise HTTPException(503, "Tautulli not configured")

    entry_date = row[0]
    date_str = entry_date.strftime("%Y-%m-%d")

    try:
        resp = httpx.get(
            f"{settings.tautulli_url}/api/v2",
            params={
                "apikey": settings.tautulli_api_key,
                "cmd": "get_history",
                "length": 50,
                "start_date": date_str,
            },
            timeout=10,
        )
        resp.raise_for_status()
        records = resp.json().get("response", {}).get("data", {}).get("data", [])
    except Exception as e:
        raise HTTPException(502, f"Tautulli error: {e}")

    imported = 0
    total = 0
    for r in records:
        media_type = r.get("media_type", "")
        if media_type not in ("movie", "episode"):
            continue
        total += 1

        title = r.get("full_title") or r.get("title")
        watched_at = datetime.fromtimestamp(r["date"], tz=timezone.utc) if r.get("date") else None
        session_key = str(r.get("reference_id", "")) if r.get("reference_id") else None

        cur.execute(
            """INSERT INTO media_watch
                   (entry_id, title, media_type, series_title, season, episode,
                    platform, tautulli_session_key, watched_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (entry_id, tautulli_session_key)
                   WHERE tautulli_session_key IS NOT NULL
               DO NOTHING""",
            (entry_id, title, media_type, r.get("grandparent_title"),
             r.get("parent_media_index"), r.get("media_index"),
             r.get("platform"), session_key, watched_at),
        )
        imported += cur.rowcount

    conn.commit()
    return {"imported": imported, "total_on_date": total}
