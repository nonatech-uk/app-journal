"""Daily summary enrichment — consolidate structured data and top up from sources."""

import logging
import uuid as uuid_mod
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


def _backfill_mbids(conn, scrobble_dsn: str, entry_id: int) -> int:
    """Populate recording_mbid and artist_mbid on music rows from the scrobble link table."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, lower(artist) AS artist_lower, lower(track) AS track_lower "
        "FROM music WHERE entry_id = %s AND recording_mbid IS NULL AND source = 'scrobble'",
        (entry_id,),
    )
    rows_to_update = cur.fetchall()
    if not rows_to_update:
        return 0

    pairs = [(r[1], r[2]) for r in rows_to_update]
    # Build a single query to look up all pairs
    conditions = " OR ".join(
        ["(sl.artist_string = %s AND sl.track_string = %s)"] * len(pairs)
    )
    params: list = []
    for a, t in pairs:
        params.extend([a, t])

    links = _safe_query(
        scrobble_dsn,
        f"""SELECT sl.artist_string, sl.track_string,
                   sl.artist_mbid::text, sl.recording_mbid::text,
                   mr.spotify_track_id
            FROM music_scrobble_link sl
            LEFT JOIN music_recording mr ON mr.mbid = sl.recording_mbid
            WHERE sl.recording_mbid IS NOT NULL AND ({conditions})""",
        tuple(params),
    )

    link_map = {(r["artist_string"], r["track_string"]): r for r in links}
    updated = 0
    for music_id, artist_lower, track_lower in rows_to_update:
        link = link_map.get((artist_lower, track_lower))
        if link:
            cur.execute(
                "UPDATE music SET recording_mbid = %s, artist_mbid = %s, spotify_track_id = %s WHERE id = %s",
                (link["recording_mbid"], link["artist_mbid"], link.get("spotify_track_id"), music_id),
            )
            updated += cur.rowcount
    return updated


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

        # Backfill MBIDs from enrichment link table
        _backfill_mbids(conn, scrobble_dsn, canonical_entry_id)

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

    # Flights — commercial (local table)
    cur.execute("SELECT id FROM flight WHERE date = %s AND is_route = FALSE", (target_date,))
    imported = 0
    for (fid,) in cur.fetchall():
        cur.execute(
            """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
               VALUES (%s, %s, 'commercial') ON CONFLICT DO NOTHING""",
            (canonical_entry_id, fid),
        )
        imported += cur.rowcount
    stats["flights"] = imported

    # Flights — GA (local table)
    cur.execute("SELECT id FROM ga_flight WHERE date = %s", (target_date,))
    ga_imported = 0
    for (fid,) in cur.fetchall():
        cur.execute(
            """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
               VALUES (%s, %s, 'ga') ON CONFLICT DO NOTHING""",
            (canonical_entry_id, fid),
        )
        ga_imported += cur.rowcount
    stats["ga_flights"] = ga_imported

    # Rail journeys (local table)
    cur.execute("SELECT id FROM rail_journey WHERE date = %s", (target_date,))
    rail_imported = 0
    for (rid,) in cur.fetchall():
        cur.execute(
            """INSERT INTO entry_rail_journey (entry_id, rail_journey_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (canonical_entry_id, rid),
        )
        rail_imported += cur.rowcount
    stats["rail_journeys"] = rail_imported

    # Skiing days (local table)
    cur.execute("""
        SELECT id, location, duration_hours, distance_km,
               vertical_up_m, vertical_down_m, max_altitude_m
        FROM skiing_day WHERE date = %s
    """, (target_date,))
    ski_cols = [desc[0] for desc in cur.description]
    skiing_rows = [dict(zip(ski_cols, r)) for r in cur.fetchall()]
    ski_imported = 0
    for s in skiing_rows:
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
            ski_imported += cur.rowcount
    stats["skiing"] = ski_imported

    # Events (from local event table, date-matched including multi-day)
    cur.execute("""
        INSERT INTO entry_event (entry_id, event_id)
        SELECT %s, id FROM event
        WHERE event_date <= %s AND COALESCE(end_date, event_date) >= %s
        ON CONFLICT DO NOTHING
    """, (canonical_entry_id, target_date, target_date))
    stats["events"] = cur.rowcount

    # GPS start/end locations
    mylocation_dsn = (
        settings.cross_dsn(settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password)
        if settings.mylocation_db_password else None
    )
    if mylocation_dsn:
        stats["gps_locations"] = _enrich_gps_locations(
            cur, mylocation_dsn, canonical_entry_id, target_date, day_start, day_end,
        )

    # Weather per location (for GPS-enriched locations)
    stats["location_weather"] = _enrich_weather_for_locations(
        cur, canonical_entry_id, target_date,
    )

    # Immich photos
    if settings.immich_api_key:
        stats["photos"] = _enrich_immich_photos(
            cur, settings, canonical_entry_id, target_date,
        )

    return stats


def _enrich_immich_photos(
    cur, settings, entry_id: int, target_date: date, max_photos: int = 6,
) -> int:
    """Fetch photos from Immich for the target date and link as attachments."""
    # Check existing Immich attachments to avoid duplicates
    cur.execute(
        "SELECT immich_asset_id FROM attachment WHERE entry_id = %s AND immich_asset_id IS NOT NULL",
        (entry_id,),
    )
    existing_ids = {r[0] for r in cur.fetchall()}

    try:
        resp = httpx.post(
            f"{settings.immich_url}/api/search/metadata",
            json={
                "takenAfter": f"{target_date}T00:00:00.000Z",
                "takenBefore": f"{target_date}T23:59:59.999Z",
                "order": "asc",
                "size": 200,
            },
            headers={"x-api-key": settings.immich_api_key},
            timeout=30,
        )
        resp.raise_for_status()
        assets = resp.json().get("assets", {}).get("items", [])
    except Exception as e:
        log.warning("Immich search failed for %s: %s", target_date, e)
        return 0

    if not assets:
        return 0

    # Select representative photos (prefer images, spread across the day)
    images = [a for a in assets if a.get("type", "").upper() == "IMAGE"]
    if not images:
        images = assets
    all_sorted = sorted(images, key=lambda a: a.get("fileCreatedAt", ""))
    if len(all_sorted) <= max_photos:
        selected = all_sorted
    else:
        step = max(1, len(all_sorted) // max_photos)
        selected = [all_sorted[i] for i in range(0, len(all_sorted), step)][:max_photos]

    inserted = 0
    for asset in selected:
        asset_id = asset.get("id")
        if not asset_id or asset_id in existing_ids:
            continue
        att_uuid = str(uuid_mod.uuid4()).upper()
        exif = asset.get("exifInfo", {})
        original_name = asset.get("originalFileName", "")
        ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "jpeg"
        if ext in ("jpg", "heic"):
            ext = "jpeg"
        cur.execute(
            """INSERT INTO attachment
               (entry_id, uuid, type, filename, width, height,
                camera_make, camera_model, lens_model, iso, f_number,
                focal_length, date, immich_asset_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            (entry_id, att_uuid, ext, original_name,
             exif.get("exifImageWidth"), exif.get("exifImageHeight"),
             exif.get("make"), exif.get("model"), exif.get("lensModel"),
             exif.get("iso"), str(exif["fNumber"]) if exif.get("fNumber") else None,
             str(exif["focalLength"]) if exif.get("focalLength") else None,
             asset.get("fileCreatedAt"), asset_id),
        )
        inserted += cur.rowcount
    return inserted


def _place_lookup(mylocation_dsn: str, lat: float, lon: float, dt: date) -> dict:
    """Look up a covering place from the mylocation DB. Returns location fields dict."""
    rows = _safe_query(
        mylocation_dsn,
        """SELECT p.name, pt.name AS place_type
           FROM place p
           JOIN place_type pt ON pt.id = p.place_type_id
           WHERE ST_DWithin(p.geom,
                 ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                 p.distance_m)
             AND (p.date_from IS NULL OR p.date_from <= %s)
             AND (p.date_to IS NULL OR p.date_to >= %s)
           ORDER BY ST_Distance(p.geom,
                 ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)
           LIMIT 1""",
        (lon, lat, dt, dt, lon, lat),
    )
    if rows:
        return {"place_name": rows[0]["name"], "place_type": rows[0]["place_type"]}
    # Fall back to Nominatim reverse geocode
    try:
        from src.services.location import reverse_geocode
        return reverse_geocode(lat, lon)
    except Exception:
        return {}


def _enrich_weather_for_locations(cur, entry_id: int, target_date: date) -> int:
    """Fetch historical weather for each location that doesn't already have weather."""
    from src.services.weather import get_historical_weather

    cur.execute(
        """SELECT l.id, l.latitude, l.longitude, l.sequence_order
           FROM location l
           WHERE l.entry_id = %s AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM weather w WHERE w.location_id = l.id)
           ORDER BY l.sequence_order""",
        (entry_id,),
    )
    locations = cur.fetchall()
    if not locations:
        return 0

    inserted = 0
    date_str = target_date.isoformat()
    for loc_id, lat, lon, seq in locations:
        w = get_historical_weather(lat, lon, date_str)
        if not w:
            continue
        cur.execute(
            """INSERT INTO weather (entry_id, temp_celsius, conditions, weather_code,
                                    relative_humidity, wind_speed_kph, wind_bearing,
                                    pressure_mb, location_id, sequence_order)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (entry_id, w.get("temp_celsius"), w.get("conditions"), w.get("weather_code"),
             w.get("relative_humidity"), w.get("wind_speed_kph"), w.get("wind_bearing"),
             w.get("pressure_mb"), loc_id, seq),
        )
        inserted += cur.rowcount
    return inserted


def _coords_close(lat1: float, lon1: float, lat2: float, lon2: float) -> bool:
    """Return True if two points are within ~100m of each other."""
    return (lat1 - lat2) ** 2 + (lon1 - lon2) ** 2 < 0.000001


def _enrich_gps_locations(
    cur, mylocation_dsn: str, entry_id: int, target_date: date,
    day_start: datetime, day_end: datetime,
) -> int:
    """Insert start/end GPS locations for the day into the location table."""
    # Check for existing locations
    cur.execute(
        "SELECT id, latitude, longitude, location_type FROM location WHERE entry_id = %s",
        (entry_id,),
    )
    existing = cur.fetchall()
    has_primary = any(r[3] == "primary" for r in existing)
    has_secondary = any(r[3] == "secondary" for r in existing)

    # If we already have both primary and secondary, nothing to do
    if has_primary and has_secondary:
        return 0

    first = _safe_query(
        mylocation_dsn,
        """SELECT lat, lon FROM gps_points
           WHERE ts >= %s AND ts < %s AND source_type != 'tractive'
           ORDER BY ts ASC LIMIT 1""",
        (day_start, day_end),
    )
    if not first:
        return 0

    last = _safe_query(
        mylocation_dsn,
        """SELECT lat, lon FROM gps_points
           WHERE ts >= %s AND ts < %s AND source_type != 'tractive'
           ORDER BY ts DESC LIMIT 1""",
        (day_start, day_end),
    )

    fp = first[0]
    lp = last[0] if last else fp
    start_end_same = _coords_close(fp["lat"], fp["lon"], lp["lat"], lp["lon"])
    inserted = 0

    if not has_primary:
        # No existing location — insert start-of-day as primary
        place = _place_lookup(mylocation_dsn, fp["lat"], fp["lon"], target_date)
        cur.execute(
            """INSERT INTO location (entry_id, latitude, longitude, place_name,
                                     locality, country, location_type, sequence_order)
               VALUES (%s, %s, %s, %s, %s, %s, 'primary', 0)""",
            (entry_id, fp["lat"], fp["lon"],
             place.get("place_name"), place.get("locality"), place.get("country")),
        )
        inserted += cur.rowcount

        # Add end-of-day as secondary if different from start
        if not start_end_same:
            place_end = _place_lookup(mylocation_dsn, lp["lat"], lp["lon"], target_date)
            cur.execute(
                """INSERT INTO location (entry_id, latitude, longitude, place_name,
                                         locality, country, location_type, sequence_order)
                   VALUES (%s, %s, %s, %s, %s, %s, 'secondary', 1)""",
                (entry_id, lp["lat"], lp["lon"],
                 place_end.get("place_name"), place_end.get("locality"), place_end.get("country")),
            )
            inserted += cur.rowcount
    else:
        # Has primary already — only add end-of-day if different from existing
        primary = next(r for r in existing if r[3] == "primary")
        existing_lat, existing_lon = primary[1], primary[2]

        if not start_end_same and not _coords_close(existing_lat, existing_lon, lp["lat"], lp["lon"]):
            place_end = _place_lookup(mylocation_dsn, lp["lat"], lp["lon"], target_date)
            cur.execute(
                """INSERT INTO location (entry_id, latitude, longitude, place_name,
                                         locality, country, location_type, sequence_order)
                   VALUES (%s, %s, %s, %s, %s, %s, 'secondary', 1)""",
                (entry_id, lp["lat"], lp["lon"],
                 place_end.get("place_name"), place_end.get("locality"), place_end.get("country")),
            )
            inserted += cur.rowcount

    return inserted


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
            # No entries — auto-create daily_summary if GPS data or events exist
            entry_id = _auto_create_from_gps(cur, settings, target_date)
            if not entry_id:
                entry_id = _auto_create_for_events(cur, target_date)
            if entry_id:
                result["auto_created"] = True
                result["enrichment"] = enrich_from_sources(conn, settings, entry_id, target_date)
            else:
                result["skipped"] = "no entries for this date"

    conn.commit()
    return result


def _auto_create_from_gps(cur, settings, target_date: date) -> int | None:
    """Create a daily_summary entry if GPS data exists for the date. Returns entry id or None."""
    if not settings.mylocation_db_password:
        return None

    mylocation_dsn = settings.cross_dsn(
        settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password,
    )
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    count_rows = _safe_query(
        mylocation_dsn,
        "SELECT count(*) AS cnt FROM gps_points WHERE ts >= %s AND ts < %s AND source_type != 'tractive'",
        (day_start, day_end),
    )
    if not count_rows or count_rows[0]["cnt"] == 0:
        return None

    title = f"## {target_date.day} {target_date.strftime('%B')} {target_date.year}"
    cur.execute(
        """INSERT INTO entry (uuid, created_at, gregorian_year, gregorian_month, gregorian_day,
                              entry_type, is_all_day, markdown_text)
           VALUES (gen_random_uuid()::text, %s, %s, %s, %s,
                   'daily_summary', true, %s)
           RETURNING id""",
        (day_start, target_date.year, target_date.month, target_date.day, title),
    )
    row = cur.fetchone()
    log.info("Auto-created daily_summary entry %s for %s", row[0], target_date)
    return row[0]


def _auto_create_for_events(cur, target_date: date) -> int | None:
    """Create a daily_summary entry if events exist for the date. Returns entry id or None."""
    cur.execute(
        "SELECT count(*) FROM event WHERE event_date <= %s AND COALESCE(end_date, event_date) >= %s",
        (target_date, target_date),
    )
    if cur.fetchone()[0] == 0:
        return None

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    title = f"## {target_date.day} {target_date.strftime('%B')} {target_date.year}"
    cur.execute(
        """INSERT INTO entry (uuid, created_at, gregorian_year, gregorian_month, gregorian_day,
                              entry_type, is_all_day, markdown_text)
           VALUES (gen_random_uuid()::text, %s, %s, %s, %s,
                   'daily_summary', true, %s)
           RETURNING id""",
        (day_start, target_date.year, target_date.month, target_date.day, title),
    )
    row = cur.fetchone()
    log.info("Auto-created daily_summary entry %s for events on %s", row[0], target_date)
    return row[0]
