"""Daily summary enrichment — consolidate structured data and top up from sources."""

import logging
from datetime import date, datetime, timedelta, timezone

import httpx

log = logging.getLogger(__name__)


def _safe_query(dsn: str, query: str, params: tuple) -> list[dict]:
    """Execute a query against an external database, returning [] on failure."""
    try:
        import psycopg2

        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.warning("Cross-DB query failed: %s", e)
        return []


def consolidate_structured_data(conn, summary_id: int, child_ids: list[int]) -> dict:
    """Migrate structured data from child entries to the daily_summary entry.

    Returns counts of migrated rows per table.
    """
    if not child_ids:
        return {}

    cur = conn.cursor()
    stats = {}

    # Music — deduplicate scrobble_db_id before reassigning
    # 1. Remove child rows that conflict with existing summary rows
    cur.execute(
        """DELETE FROM music
           WHERE entry_id = ANY(%s) AND scrobble_db_id IS NOT NULL
             AND scrobble_db_id IN (
               SELECT scrobble_db_id FROM music
               WHERE entry_id = %s AND scrobble_db_id IS NOT NULL
             )""",
        (child_ids, summary_id),
    )
    # 2. Remove cross-sibling duplicates (keep lowest id per scrobble_db_id)
    cur.execute(
        """DELETE FROM music
           WHERE entry_id = ANY(%s) AND scrobble_db_id IS NOT NULL
             AND id NOT IN (
               SELECT MIN(id) FROM music
               WHERE entry_id = ANY(%s) AND scrobble_db_id IS NOT NULL
               GROUP BY scrobble_db_id
             )""",
        (child_ids, child_ids),
    )
    cur.execute(
        "UPDATE music SET entry_id = %s WHERE entry_id = ANY(%s)",
        (summary_id, child_ids),
    )
    stats["music"] = cur.rowcount

    # Media watches — deduplicate tautulli_session_key
    cur.execute(
        """DELETE FROM media_watch
           WHERE entry_id = ANY(%s) AND tautulli_session_key IS NOT NULL
             AND tautulli_session_key IN (
               SELECT tautulli_session_key FROM media_watch
               WHERE entry_id = %s AND tautulli_session_key IS NOT NULL
             )""",
        (child_ids, summary_id),
    )
    # Remove cross-sibling duplicates (keep lowest id per tautulli_session_key)
    cur.execute(
        """DELETE FROM media_watch
           WHERE entry_id = ANY(%s) AND tautulli_session_key IS NOT NULL
             AND id NOT IN (
               SELECT MIN(id) FROM media_watch
               WHERE entry_id = ANY(%s) AND tautulli_session_key IS NOT NULL
               GROUP BY tautulli_session_key
             )""",
        (child_ids, child_ids),
    )
    cur.execute(
        "UPDATE media_watch SET entry_id = %s WHERE entry_id = ANY(%s)",
        (summary_id, child_ids),
    )
    stats["media_watch"] = cur.rowcount

    # Activities
    cur.execute(
        "UPDATE activity SET entry_id = %s WHERE entry_id = ANY(%s)",
        (summary_id, child_ids),
    )
    stats["activity"] = cur.rowcount

    # Entry flights — composite PK includes entry_id, so DELETE + INSERT
    cur.execute(
        "SELECT flight_id, flight_type FROM entry_flight WHERE entry_id = ANY(%s)",
        (child_ids,),
    )
    flights = cur.fetchall()
    if flights:
        cur.execute("DELETE FROM entry_flight WHERE entry_id = ANY(%s)", (child_ids,))
        for flight_id, flight_type in flights:
            cur.execute(
                """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
                   VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (summary_id, flight_id, flight_type),
            )
        stats["entry_flight"] = len(flights)

    # Weather — pick first child's weather, reassign to summary, delete others
    cur.execute(
        """SELECT id, entry_id FROM weather
           WHERE entry_id = ANY(%s) ORDER BY entry_id LIMIT 1""",
        (child_ids,),
    )
    weather_row = cur.fetchone()
    if weather_row:
        # Check if summary already has weather
        cur.execute("SELECT id FROM weather WHERE entry_id = %s", (summary_id,))
        existing = cur.fetchone()
        if existing:
            # Summary already has weather — just delete children's weather
            cur.execute("DELETE FROM weather WHERE entry_id = ANY(%s)", (child_ids,))
        else:
            # Move first child's weather to summary, delete the rest
            cur.execute(
                "UPDATE weather SET entry_id = %s WHERE id = %s",
                (summary_id, weather_row[0]),
            )
            cur.execute(
                "DELETE FROM weather WHERE entry_id = ANY(%s)",
                (child_ids,),
            )
        stats["weather"] = 1

    return stats


def enrich_from_sources(conn, settings, canonical_entry_id: int, target_date: date) -> dict:
    """Top up structured data from authoritative sources for a single day.

    Returns counts of inserted rows per source.
    """
    cur = conn.cursor()
    stats = {}
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # Scrobbles
    if settings.scrobble_db_password:
        scrobble_dsn = settings.cross_dsn(
            settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password
        )
        rows = _safe_query(
            scrobble_dsn,
            """SELECT s.id, ar.name AS artist, t.title AS track,
                      t.album_title AS album, s.listened_at
               FROM scrobble s
               JOIN track t ON t.id = s.track_id
               JOIN track_artist ta ON ta.track_id = t.id
               JOIN artist ar ON ar.id = ta.artist_id
               WHERE s.listened_at >= %s AND s.listened_at < %s
               ORDER BY s.listened_at""",
            (day_start, day_end),
        )
        imported = 0
        for row in rows:
            cur.execute(
                """INSERT INTO music (entry_id, track, artist, album, played_at, source, scrobble_db_id)
                   VALUES (%s, %s, %s, %s, %s, 'scrobble', %s)
                   ON CONFLICT (entry_id, scrobble_db_id) WHERE scrobble_db_id IS NOT NULL
                   DO NOTHING""",
                (canonical_entry_id, row["track"], row["artist"], row["album"],
                 row["listened_at"], row["id"]),
            )
            imported += cur.rowcount
        stats["scrobbles"] = imported

    # Tautulli watches
    if settings.tautulli_api_key:
        try:
            date_str = target_date.isoformat()
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
            imported = 0
            for r in records:
                media_type = r.get("media_type", "")
                if media_type not in ("movie", "episode"):
                    continue
                title = r.get("full_title") or r.get("title")
                watched_at = (
                    datetime.fromtimestamp(r["date"], tz=timezone.utc)
                    if r.get("date")
                    else None
                )
                session_key = str(r.get("reference_id", "")) if r.get("reference_id") else None
                season = r.get("parent_media_index") or None
                episode = r.get("media_index") or None
                cur.execute(
                    """INSERT INTO media_watch
                           (entry_id, title, media_type, series_title, season, episode,
                            platform, tautulli_session_key, watched_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (entry_id, tautulli_session_key)
                           WHERE tautulli_session_key IS NOT NULL
                       DO NOTHING""",
                    (canonical_entry_id, title, media_type, r.get("grandparent_title") or None,
                     season, episode,
                     r.get("platform"), session_key, watched_at),
                )
                imported += cur.rowcount
            stats["watches"] = imported
        except Exception as e:
            log.warning("Tautulli query failed: %s", e)

    # Flights (commercial)
    mylocation_dsn = None
    if settings.mylocation_db_password:
        mylocation_dsn = settings.cross_dsn(
            settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password
        )
        flights = _safe_query(
            mylocation_dsn,
            """SELECT id FROM flights
               WHERE date = %s AND is_route = FALSE""",
            (target_date,),
        )
        imported = 0
        for f in flights:
            cur.execute(
                """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
                   VALUES (%s, %s, 'commercial')
                   ON CONFLICT DO NOTHING""",
                (canonical_entry_id, f["id"]),
            )
            imported += cur.rowcount
        stats["flights"] = imported

        # GA flights
        ga_flights = _safe_query(
            mylocation_dsn,
            "SELECT id FROM ga_flights WHERE date = %s",
            (target_date,),
        )
        ga_imported = 0
        for f in ga_flights:
            cur.execute(
                """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
                   VALUES (%s, %s, 'ga')
                   ON CONFLICT DO NOTHING""",
                (canonical_entry_id, f["id"]),
            )
            ga_imported += cur.rowcount
        stats["ga_flights"] = ga_imported

    # Skiing days
    if mylocation_dsn:
        skiing_rows = _safe_query(
            mylocation_dsn,
            """SELECT id, date, location, duration_hours, distance_km,
                      vertical_up_m, vertical_down_m, max_speed_kmh,
                      max_altitude_m, num_runs, num_lifts
               FROM skiing_days WHERE date = %s""",
            (target_date,),
        )
        imported = 0
        for s in skiing_rows:
            # Check if already linked via skiing_day_id
            cur.execute(
                "SELECT id FROM activity WHERE entry_id = %s AND skiing_day_id = %s",
                (canonical_entry_id, s["id"]),
            )
            if not cur.fetchone():
                cur.execute(
                    """INSERT INTO activity
                           (entry_id, activity_type, title, skiing_day_id,
                            distance_km, duration_seconds,
                            elevation_gain, elevation_loss, max_altitude)
                       VALUES (%s, 'skiing', %s, %s, %s, %s, %s, %s, %s)""",
                    (canonical_entry_id, s["location"], s["id"],
                     s.get("distance_km"), int(s["duration_hours"] * 3600) if s.get("duration_hours") else None,
                     s.get("vertical_up_m"), s.get("vertical_down_m"), s.get("max_altitude_m")),
                )
                imported += cur.rowcount
        stats["skiing"] = imported

    return stats


def run_daily_enrichment(conn, settings, target_date: date | None = None) -> dict:
    """Run the daily enrichment job for a single date.

    Default: yesterday. Consolidates multi-entry days and enriches from sources.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    cur = conn.cursor()
    result = {"date": target_date.isoformat(), "consolidation": {}, "enrichment": {}}

    # Find explicit daily_summary entries for this date
    cur.execute(
        """SELECT id FROM entry
           WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
             AND entry_type = 'daily_summary'""",
        (target_date.year, target_date.month, target_date.day),
    )
    summary_row = cur.fetchone()

    if summary_row:
        summary_id = summary_row[0]
        # Get child entry IDs
        cur.execute(
            "SELECT id FROM entry WHERE parent_entry_id = %s ORDER BY created_at",
            (summary_id,),
        )
        child_ids = [r[0] for r in cur.fetchall()]

        # Task A: consolidate structured data
        result["consolidation"] = consolidate_structured_data(conn, summary_id, child_ids)
        # Task B: enrich from sources
        result["enrichment"] = enrich_from_sources(conn, settings, summary_id, target_date)
    else:
        # Single-entry day (implicit summary) — just enrich
        cur.execute(
            """SELECT id FROM entry
               WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
                 AND entry_type IN ('diary', 'retrospective')
                 AND parent_entry_id IS NULL""",
            (target_date.year, target_date.month, target_date.day),
        )
        row = cur.fetchone()
        if row:
            result["enrichment"] = enrich_from_sources(conn, settings, row[0], target_date)
        else:
            result["skipped"] = "no entries for this date"

    conn.commit()
    return result
