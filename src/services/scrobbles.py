"""Scrobble service — recent music from the scrobble database."""

import psycopg2


def get_recent_scrobbles(settings, minutes: int = 30, limit: int = 5) -> list[dict]:
    """Get the most recent scrobbles within the last N minutes."""
    dsn = settings.cross_dsn(
        settings.scrobble_db_name,
        settings.scrobble_db_user,
        settings.scrobble_db_password,
    )
    if not settings.scrobble_db_password:
        return []
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            """SELECT a.name AS artist, t.title AS track, t.album_title AS album,
                      s.listened_at
               FROM scrobble s
               JOIN track t ON t.id = s.track_id
               JOIN track_artist ta ON ta.track_id = t.id
               JOIN artist a ON a.id = ta.artist_id
               WHERE s.listened_at >= now() - interval '%s minutes'
               ORDER BY s.listened_at DESC
               LIMIT %s""",
            (minutes, limit),
        )
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []
