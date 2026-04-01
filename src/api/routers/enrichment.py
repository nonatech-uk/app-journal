"""Cross-service enrichment — aggregates context from other databases and APIs."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_conn, get_current_user

router = APIRouter()


def _safe_query(dsn: str, query: str, params: tuple):
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
    except Exception:
        return []


def _nominatim_reverse(lat: float, lon: float) -> str | None:
    """Reverse geocode via Nominatim, returning the first part of display_name."""
    try:
        import httpx
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 16},
            headers={"User-Agent": "journal-app/1.0 (personal use)"},
            timeout=10,
        )
        resp.raise_for_status()
        name = resp.json().get("display_name", "").split(",")[0].strip()
        return name or None
    except Exception:
        return None


@router.get("/entries/{entry_id}/enrichment")
def get_enrichment(entry_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    from config.settings import settings

    cur = conn.cursor()
    cur.execute("SELECT created_at, timezone FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")

    entry_date = row[0]
    day_start = entry_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    result = {
        "scrobbles": [],
        "transactions": [],
        "gps_summary": None,
        "tautulli_watches": [],
        "flights": [],
        "skiing": [],
        "watches": [],
    }

    # Scrobbles (±2 hours around entry time)
    scrobble_dsn = settings.cross_dsn(settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password)
    if settings.scrobble_db_password:
        result["scrobbles"] = _safe_query(
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

        # Check which are already imported into music table
        cur.execute(
            "SELECT scrobble_db_id FROM music WHERE entry_id = %s AND scrobble_db_id IS NOT NULL",
            (entry_id,),
        )
        linked_scrobbles = {r[0] for r in cur.fetchall()}
        for s in result["scrobbles"]:
            s["linked"] = s["id"] in linked_scrobbles

    # Transactions (same day)
    finance_dsn = settings.cross_dsn(settings.finance_db_name, settings.finance_db_user, settings.finance_db_password)
    if settings.finance_db_password:
        result["transactions"] = _safe_query(
            finance_dsn,
            """SELECT ct.merchant_name, ct.amount, ct.currency,
                      ct.posted_at, cat.full_path as category
               FROM cleaned_transaction ct
               LEFT JOIN canonical_merchant cm ON cm.id = ct.canonical_merchant_id
               LEFT JOIN category cat ON cat.id = ct.category_id
               WHERE ct.posted_at::date = %s::date
               ORDER BY ct.posted_at""",
            (entry_date,),
        )

    # GPS track (same day) — start/end places + track thumbnail URL
    mylocation_dsn = settings.cross_dsn(settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password)
    if settings.mylocation_db_password:
        gps_track = {"point_count": 0, "start_place": None, "end_place": None,
                     "start_place_type": None, "end_place_type": None,
                     "track_url": None, "track_svg_url": None}

        count_rows = _safe_query(
            mylocation_dsn,
            """SELECT count(*) AS cnt FROM gps_points
               WHERE ts >= %s AND ts < %s AND source_type != 'tractive'""",
            (day_start, day_end),
        )
        point_count = count_rows[0]["cnt"] if count_rows else 0
        gps_track["point_count"] = point_count

        if point_count > 0:
            date_str = entry_date.strftime("%Y-%m-%d")
            base = settings.mylocation_public_url.rstrip("/")
            gps_track["track_url"] = f"{base}/explorer?date={date_str}"
            gps_track["track_svg_url"] = f"{base}/api/v1/gps/track-svg?date={date_str}"

            # Start-of-day place
            first = _safe_query(
                mylocation_dsn,
                """SELECT lat, lon FROM gps_points
                   WHERE ts >= %s AND ts < %s AND source_type != 'tractive'
                   ORDER BY ts ASC LIMIT 1""",
                (day_start, day_end),
            )
            if first:
                fp = first[0]
                place = _safe_query(
                    mylocation_dsn,
                    """SELECT p.name, pt.name AS place_type
                       FROM place p JOIN place_type pt ON pt.id = p.place_type_id
                       WHERE ST_DWithin(p.geom,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                             p.distance_m)
                         AND (p.date_from IS NULL OR p.date_from <= %s)
                         AND (p.date_to IS NULL OR p.date_to >= %s)
                       ORDER BY ST_Distance(p.geom,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)
                       LIMIT 1""",
                    (fp["lon"], fp["lat"], entry_date, entry_date, fp["lon"], fp["lat"]),
                )
                if place:
                    gps_track["start_place"] = place[0]["name"]
                    gps_track["start_place_type"] = place[0]["place_type"]
                else:
                    geo = _nominatim_reverse(fp["lat"], fp["lon"])
                    if geo:
                        gps_track["start_place"] = geo

            # End-of-day place
            last = _safe_query(
                mylocation_dsn,
                """SELECT lat, lon FROM gps_points
                   WHERE ts >= %s AND ts < %s AND source_type != 'tractive'
                   ORDER BY ts DESC LIMIT 1""",
                (day_start, day_end),
            )
            if last:
                lp = last[0]
                place = _safe_query(
                    mylocation_dsn,
                    """SELECT p.name, pt.name AS place_type
                       FROM place p JOIN place_type pt ON pt.id = p.place_type_id
                       WHERE ST_DWithin(p.geom,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                             p.distance_m)
                         AND (p.date_from IS NULL OR p.date_from <= %s)
                         AND (p.date_to IS NULL OR p.date_to >= %s)
                       ORDER BY ST_Distance(p.geom,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)
                       LIMIT 1""",
                    (lp["lon"], lp["lat"], entry_date, entry_date, lp["lon"], lp["lat"]),
                )
                if place:
                    gps_track["end_place"] = place[0]["name"]
                    gps_track["end_place_type"] = place[0]["place_type"]
                else:
                    geo = _nominatim_reverse(lp["lat"], lp["lon"])
                    if geo:
                        gps_track["end_place"] = geo

        result["gps_track"] = gps_track
        result["gps_summary"] = None  # deprecated, kept for backward compat

    # Flights (same day, exclude route records)
    if settings.mylocation_db_password:
        result["flights"] = _safe_query(
            mylocation_dsn,
            """SELECT id, date, flight_number, dep_airport, dep_airport_name,
                      arr_airport, arr_airport_name, dep_time, arr_time, duration,
                      airline, aircraft_type, registration, seat_number,
                      flight_class, distance_km, source
               FROM flights
               WHERE date = %s::date AND is_route = FALSE
               ORDER BY dep_time NULLS LAST""",
            (entry_date,),
        )

        # Also check already-linked flights for this entry
        cur.execute(
            "SELECT flight_id, flight_type FROM entry_flight WHERE entry_id = %s",
            (entry_id,),
        )
        linked = {(r[0], r[1]) for r in cur.fetchall()}
        for f in result["flights"]:
            f["linked"] = (f["id"], "commercial") in linked

    # Skiing days (same day)
    if settings.mylocation_db_password:
        skiing_rows = _safe_query(
            mylocation_dsn,
            """SELECT id, date, location, duration_hours, distance_km,
                      vertical_up_m, vertical_down_m, max_speed_kmh,
                      max_altitude_m, num_runs, num_lifts, season
               FROM skiing_days
               WHERE date = %s::date""",
            (entry_date,),
        )
        # Check which are already linked via activity table
        cur.execute(
            "SELECT skiing_day_id FROM activity WHERE entry_id = %s AND skiing_day_id IS NOT NULL",
            (entry_id,),
        )
        linked_skiing = {r[0] for r in cur.fetchall()}
        for s in skiing_rows:
            s["linked"] = s["id"] in linked_skiing
        result["skiing"] = skiing_rows

    # Tautulli watches (same day, movies + episodes only)
    if settings.tautulli_api_key:
        try:
            import httpx
            from datetime import datetime as dt

            date_str = entry_date.strftime("%Y-%m-%d")
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

            watches = []
            for r in records:
                media_type = r.get("media_type", "")
                if media_type not in ("movie", "episode"):
                    continue
                watches.append({
                    "title": r.get("full_title") or r.get("title"),
                    "media_type": media_type,
                    "series_title": r.get("grandparent_title"),
                    "season": r.get("parent_media_index"),
                    "episode": r.get("media_index"),
                    "year": r.get("year"),
                    "reference_id": r.get("reference_id"),
                    "watched_at": r.get("date"),
                    "platform": r.get("platform"),
                    "percent_complete": r.get("percent_complete"),
                    "rating_key": r.get("rating_key"),
                })

            # Check which are already linked
            cur.execute(
                "SELECT tautulli_session_key FROM media_watch WHERE entry_id = %s AND tautulli_session_key IS NOT NULL",
                (entry_id,),
            )
            linked_watches = {r[0] for r in cur.fetchall()}
            for w in watches:
                w["linked"] = str(w.get("reference_id", "")) in linked_watches

            result["watches"] = watches
        except Exception:
            pass

    return result
