"""Retrospective backfill pipeline — discover dates with activity data and create journal entries."""

import time
import uuid as uuid_mod
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import httpx
import psycopg2

from src.services.location import reverse_geocode
from src.services.weather import get_historical_weather


def _safe_query(dsn: str, query: str, params: tuple) -> list[dict]:
    """Execute a query against an external database, returning [] on failure."""
    try:
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


@dataclass
class DayData:
    date: date
    flights: list[dict] = field(default_factory=list)
    ga_flights: list[dict] = field(default_factory=list)
    rail_journeys: list[dict] = field(default_factory=list)
    skiing: list[dict] = field(default_factory=list)
    scrobbles: list[dict] = field(default_factory=list)
    watches: list[dict] = field(default_factory=list)
    photos: list[dict] = field(default_factory=list)
    location: dict | None = None
    weather: dict | None = None


def discover_candidate_dates(
    settings,
    http_client: httpx.Client,
    start_date: date | None = None,
    end_date: date | None = None,
    conn=None,
) -> dict[str, set[date]]:
    """Return dates with activity per source. Keys: immich, flights, ga_flights, skiing, scrobbles."""
    sd = start_date or date(1980, 1, 1)
    ed = end_date or date.today()
    sources: dict[str, set[date]] = {}

    mylocation_dsn = settings.cross_dsn(settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password)
    scrobble_dsn = settings.cross_dsn(settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password)

    # Commercial flights (local journal DB table)
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT date FROM flight WHERE is_route = FALSE AND date BETWEEN %s AND %s", (sd, ed))
        sources["flights"] = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT DISTINCT date FROM ga_flight WHERE date BETWEEN %s AND %s", (sd, ed))
        sources["ga_flights"] = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT DISTINCT date FROM rail_journey WHERE date BETWEEN %s AND %s", (sd, ed))
        sources["rail_journeys"] = {r[0] for r in cur.fetchall()}

    # Skiing days (local table)
    if conn:
        cur.execute("SELECT DISTINCT date FROM skiing_day WHERE date BETWEEN %s AND %s", (sd, ed))
        sources["skiing"] = {r[0] for r in cur.fetchall()}

    # Scrobbles
    if settings.scrobble_db_password:
        rows = _safe_query(scrobble_dsn,
            "SELECT DISTINCT listened_at::date AS date FROM scrobble WHERE listened_at::date BETWEEN %s AND %s",
            (sd, ed))
        sources["scrobbles"] = {r["date"] for r in rows}

    # Immich photos
    immich_dates: set[date] = set()
    if settings.immich_api_key:
        page = 1
        while True:
            try:
                resp = http_client.post(
                    f"{settings.immich_url}/api/search/metadata",
                    json={
                        "takenAfter": f"{sd}T00:00:00.000Z",
                        "takenBefore": f"{ed}T23:59:59.999Z",
                        "order": "asc",
                        "size": 1000,
                        "page": page,
                    },
                    headers={"x-api-key": settings.immich_api_key},
                    timeout=30,
                )
                resp.raise_for_status()
                items = resp.json().get("assets", {}).get("items", [])
                if not items:
                    break
                for asset in items:
                    dt_str = asset.get("fileCreatedAt", "")[:10]
                    if dt_str:
                        try:
                            immich_dates.add(date.fromisoformat(dt_str))
                        except ValueError:
                            pass
                if len(items) < 1000:
                    break
                page += 1
            except Exception:
                break
    sources["immich"] = immich_dates

    return sources


def filter_missing_dates(conn, candidate_dates: set[date]) -> list[date]:
    """Remove dates that already have a journal entry."""
    if not candidate_dates:
        return []
    cur = conn.cursor()
    date_list = sorted(candidate_dates)
    cur.execute(
        "SELECT DISTINCT created_at::date FROM entry WHERE created_at::date = ANY(%s)",
        (date_list,),
    )
    existing = {r[0] for r in cur.fetchall()}
    return sorted(candidate_dates - existing)


def collect_day_data(
    settings,
    http_client: httpx.Client,
    d: date,
    conn=None,
) -> DayData:
    """Gather all data for a single date from all sources."""
    day = DayData(date=d)
    mylocation_dsn = settings.cross_dsn(settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password)
    cur = conn.cursor() if conn else None
    scrobble_dsn = settings.cross_dsn(settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password)

    # Commercial flights (local journal DB table)
    if cur:
        cur.execute("""
            SELECT id, date, flight_number, dep_airport, dep_airport_name,
                   arr_airport, arr_airport_name, dep_time, arr_time, duration,
                   airline, aircraft_type, registration, distance_km,
                   dep_lat, dep_lon, arr_lat, arr_lon
            FROM flight WHERE date = %s AND is_route = FALSE
            ORDER BY dep_time NULLS LAST
        """, (d,))
        cols = [desc[0] for desc in cur.description]
        day.flights = [dict(zip(cols, r)) for r in cur.fetchall()]

        # GA flights (local journal DB table)
        cur.execute("""
            SELECT id, date, aircraft_type, registration, captain,
                   operating_capacity, dep_airport, arr_airport,
                   dep_time, arr_time, hours_total, exercise, comments
            FROM ga_flight WHERE date = %s
            ORDER BY dep_time NULLS LAST
        """, (d,))
        ga_cols = [desc[0] for desc in cur.description]
        day.ga_flights = [dict(zip(ga_cols, r)) for r in cur.fetchall()]

        # Rail journeys (local journal DB table)
        cur.execute("""
            SELECT id, date, time, from_station, from_code, to_station, to_code,
                   operator, train, via
            FROM rail_journey WHERE date = %s
            ORDER BY time NULLS LAST
        """, (d,))
        rj_cols = [desc[0] for desc in cur.description]
        day.rail_journeys = [dict(zip(rj_cols, r)) for r in cur.fetchall()]

    # Skiing (local journal DB table)
    if cur:
        cur.execute("""
            SELECT id, date, location, duration_hours, distance_km,
                   vertical_up_m, vertical_down_m, max_speed_kmh,
                   max_altitude_m, num_runs, num_lifts, season
            FROM skiing_day WHERE date = %s
        """, (d,))
        sk_cols = [desc[0] for desc in cur.description]
        day.skiing = [dict(zip(sk_cols, r)) for r in cur.fetchall()]

    # Scrobbles
    if settings.scrobble_db_password:
        day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        day.scrobbles = _safe_query(scrobble_dsn,
            """SELECT s.id, ar.name AS artist, t.title AS track,
                      t.album_title AS album, s.listened_at
               FROM scrobble s
               JOIN track t ON t.id = s.track_id
               JOIN track_artist ta ON ta.track_id = t.id
               JOIN artist ar ON ar.id = ta.artist_id
               WHERE s.listened_at >= %s AND s.listened_at < %s
               ORDER BY s.listened_at""",
            (day_start, day_end))

    # Tautulli watches
    if settings.tautulli_api_key:
        try:
            resp = http_client.get(
                f"{settings.tautulli_url}/api/v2",
                params={
                    "apikey": settings.tautulli_api_key,
                    "cmd": "get_history",
                    "length": 50,
                    "start_date": d.isoformat(),
                },
                timeout=10,
            )
            resp.raise_for_status()
            records = resp.json().get("response", {}).get("data", {}).get("data", [])
            for r in records:
                if r.get("media_type") in ("movie", "episode"):
                    day.watches.append({
                        "title": r.get("full_title") or r.get("title"),
                        "media_type": r.get("media_type"),
                        "series_title": r.get("grandparent_title"),
                        "season": r.get("parent_media_index"),
                        "episode": r.get("media_index"),
                        "year": r.get("year"),
                        "reference_id": r.get("reference_id"),
                        "watched_at": r.get("date"),
                        "platform": r.get("platform"),
                    })
        except Exception:
            pass

    # Immich photos
    if settings.immich_api_key:
        try:
            resp = http_client.post(
                f"{settings.immich_url}/api/search/metadata",
                json={
                    "takenAfter": f"{d}T00:00:00.000Z",
                    "takenBefore": f"{d}T23:59:59.999Z",
                    "order": "asc",
                    "size": 200,
                },
                headers={"x-api-key": settings.immich_api_key},
                timeout=30,
            )
            resp.raise_for_status()
            day.photos = resp.json().get("assets", {}).get("items", [])
        except Exception:
            pass

    # Derive location
    day.location = _derive_location(settings, day, mylocation_dsn)

    return day


def _derive_location(settings, day: DayData, mylocation_dsn: str) -> dict | None:
    """Try to find a location for the day: photo GPS > flight airport > daily_location."""
    # 1. Photo GPS
    for photo in day.photos:
        exif = photo.get("exifInfo", {})
        lat = exif.get("latitude")
        lon = exif.get("longitude")
        if lat and lon:
            geo = reverse_geocode(lat, lon)
            time.sleep(1)  # Nominatim rate limit
            return {
                "latitude": lat, "longitude": lon,
                "place_name": geo.get("place_name"),
                "locality": geo.get("locality"),
                "admin_area": geo.get("admin_area"),
                "country": geo.get("country"),
            }

    # 2. Flight departure airport coords
    for f in day.flights:
        lat = f.get("dep_lat")
        lon = f.get("dep_lon")
        if lat and lon:
            geo = reverse_geocode(lat, lon)
            time.sleep(1)
            return {
                "latitude": lat, "longitude": lon,
                "place_name": f.get("dep_airport_name") or geo.get("place_name"),
                "locality": geo.get("locality"),
                "admin_area": geo.get("admin_area"),
                "country": geo.get("country"),
            }

    # 3. GPS points average for the day
    if settings.mylocation_db_password:
        rows = _safe_query(mylocation_dsn,
            """SELECT avg(lat) AS lat, avg(lon) AS lon
               FROM gps_points
               WHERE ts::date = %s AND lat IS NOT NULL""",
            (day.date,))
        if rows and rows[0].get("lat"):
            lat = float(rows[0]["lat"])
            lon = float(rows[0]["lon"])
            geo = reverse_geocode(lat, lon)
            time.sleep(1)
            return {
                "latitude": lat, "longitude": lon,
                "place_name": geo.get("place_name"),
                "locality": geo.get("locality"),
                "admin_area": geo.get("admin_area"),
                "country": geo.get("country"),
            }

    return None


def select_representative_photos(assets: list[dict], max_photos: int = 6) -> list[dict]:
    """Pick a representative sample of photos from a day's assets."""
    # Filter to images
    images = [a for a in assets if a.get("type", "").upper() == "IMAGE"]
    if not images:
        images = assets  # fall back to all if no images

    if len(images) <= max_photos:
        return images

    # Prefer assets with GPS
    with_gps = [a for a in images if a.get("exifInfo", {}).get("latitude")]
    without_gps = [a for a in images if not a.get("exifInfo", {}).get("latitude")]

    # Spread across the day by sorting by time and picking evenly spaced
    all_sorted = sorted(images, key=lambda a: a.get("fileCreatedAt", ""))
    step = max(1, len(all_sorted) // max_photos)
    selected = [all_sorted[i] for i in range(0, len(all_sorted), step)][:max_photos]

    # Ensure at least one GPS photo if available
    if with_gps and not any(a.get("exifInfo", {}).get("latitude") for a in selected):
        selected[-1] = with_gps[0]

    return selected


def generate_markdown(day_data: DayData) -> str:
    """Build a structured markdown summary for the day."""
    d = day_data.date
    header = d.strftime("%A, %-d %B %Y")
    lines = [f"# {header}", ""]

    # Location quote
    if day_data.location:
        loc = day_data.location
        parts = [p for p in [loc.get("place_name"), loc.get("country")] if p]
        if parts:
            lines.append(f"> {', '.join(parts)}")
            lines.append("")

    # Flights
    all_flights = []
    for f in day_data.flights:
        fn = f.get("flight_number") or ""
        dep = f.get("dep_airport", "?")
        arr = f.get("arr_airport", "?")
        detail = f.get("airline") or ""
        if f.get("aircraft_type"):
            detail += f", {f['aircraft_type']}" if detail else f['aircraft_type']
        entry = f"- **{fn}**: {dep} → {arr}" if fn else f"- {dep} → {arr}"
        if detail:
            entry += f" ({detail})"
        all_flights.append(entry)
    for f in day_data.ga_flights:
        reg = f.get("registration") or ""
        dep = f.get("dep_airport") or "?"
        arr = f.get("arr_airport") or "?"
        atype = f.get("aircraft_type") or ""
        hours = f.get("hours_total")
        entry = f"- GA {reg}: {dep} → {arr}"
        if atype:
            entry += f" ({atype})"
        if hours:
            entry += f" — {hours}h"
        all_flights.append(entry)
    if all_flights:
        lines.append("## Flights")
        lines.extend(all_flights)
        lines.append("")

    # Rail journeys
    if day_data.rail_journeys:
        lines.append("## Rail")
        for rj in day_data.rail_journeys:
            fr = rj.get("from_station", "?")
            to = rj.get("to_station", "?")
            op = rj.get("operator") or ""
            entry = f"- {fr} → {to}"
            if op:
                entry += f" ({op})"
            if rj.get("time"):
                t = rj["time"]
                time_str = t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[:5]
                entry += f" at {time_str}"
            lines.append(entry)
        lines.append("")

    # Skiing
    if day_data.skiing:
        lines.append("## Skiing")
        for s in day_data.skiing:
            loc = s.get("location") or "Unknown"
            parts = []
            if s.get("vertical_down_m"):
                parts.append(f"{s['vertical_down_m']:,}m vertical")
            if s.get("num_runs"):
                parts.append(f"{s['num_runs']} runs")
            if s.get("distance_km"):
                parts.append(f"{s['distance_km']} km")
            lines.append(f"- {loc}: {', '.join(parts)}" if parts else f"- {loc}")
        lines.append("")

    # Music
    if day_data.scrobbles:
        lines.append("## Music")
        artists = Counter(s["artist"] for s in day_data.scrobbles)
        top = [a for a, _ in artists.most_common(5)]
        lines.append(f"Top artists: {', '.join(top)}")
        lines.append(f"{len(day_data.scrobbles)} tracks played.")
        lines.append("")

    # Watched
    if day_data.watches:
        lines.append("## Watched")
        for w in day_data.watches:
            title = w.get("title", "Unknown")
            year = w.get("year")
            line = f"- {title}"
            if year:
                line += f" ({year})"
            lines.append(line)
        lines.append("")

    # Photos
    if day_data.photos:
        lines.append(f"{len(day_data.photos)} photos taken.")
        lines.append("")

    return "\n".join(lines)


def create_retrospective_entry(
    conn,
    settings,
    http_client: httpx.Client,
    day_data: DayData,
    markdown: str,
    max_photos: int = 5,
    skip_photos: bool = False,
    skip_weather: bool = False,
    dry_run: bool = False,
) -> int | None:
    """Create entry + location + weather + link flights/skiing/scrobbles/watches/photos."""
    d = day_data.date
    entry_uuid = str(uuid_mod.uuid4()).upper()
    created_at = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=timezone.utc)

    if dry_run:
        return None

    cur = conn.cursor()

    # 1. Insert entry
    cur.execute(
        """INSERT INTO entry (uuid, created_at, modified_at, markdown_text,
                              is_all_day, entry_type, timezone,
                              gregorian_year, gregorian_month, gregorian_day)
           VALUES (%s, %s, now(), %s, TRUE, 'retrospective', 'UTC', %s, %s, %s)
           RETURNING id""",
        (entry_uuid, created_at, markdown, d.year, d.month, d.day),
    )
    row = cur.fetchone()
    if not row:
        conn.rollback()
        return None
    entry_id = row[0]

    # 2. Location
    if day_data.location and day_data.location.get("latitude"):
        loc = day_data.location
        cur.execute(
            """INSERT INTO location (entry_id, latitude, longitude, place_name,
                                     locality, admin_area, country, location_type)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'primary')""",
            (entry_id, loc.get("latitude"), loc.get("longitude"),
             loc.get("place_name"), loc.get("locality"),
             loc.get("admin_area"), loc.get("country")),
        )

    # 3. Weather
    if not skip_weather and day_data.location:
        lat = day_data.location.get("latitude")
        lon = day_data.location.get("longitude")
        if lat and lon:
            weather = get_historical_weather(lat, lon, d.isoformat())
            time.sleep(0.5)
            if weather:
                cur.execute(
                    """INSERT INTO weather (entry_id, temp_celsius, conditions,
                                            weather_code, wind_speed_kph)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (entry_id, weather.get("temp_celsius"), weather.get("conditions"),
                     weather.get("weather_code"), weather.get("wind_speed_kph")),
                )

    # 4. Link commercial flights
    for f in day_data.flights:
        cur.execute(
            """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
               VALUES (%s, %s, 'commercial') ON CONFLICT DO NOTHING""",
            (entry_id, f["id"]),
        )

    # 5. Link GA flights
    for f in day_data.ga_flights:
        cur.execute(
            """INSERT INTO entry_flight (entry_id, flight_id, flight_type)
               VALUES (%s, %s, 'ga') ON CONFLICT DO NOTHING""",
            (entry_id, f["id"]),
        )

    # 5b. Link rail journeys
    for rj in day_data.rail_journeys:
        cur.execute(
            """INSERT INTO entry_rail_journey (entry_id, rail_journey_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (entry_id, rj["id"]),
        )

    # 6. Link skiing
    for s in day_data.skiing:
        cur.execute(
            "SELECT id FROM activity WHERE entry_id = %s AND skiing_day_id = %s",
            (entry_id, s["id"]),
        )
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO activity (entry_id, activity_type, title, skiing_day_id,
                                         distance_km, duration_seconds, elevation_gain,
                                         elevation_loss, max_altitude)
                   VALUES (%s, 'skiing', %s, %s, %s, %s, %s, %s, %s)""",
                (entry_id, s.get("location") or "Skiing", s["id"],
                 s.get("distance_km"),
                 int(float(s["duration_hours"]) * 3600) if s.get("duration_hours") else None,
                 s.get("vertical_up_m"), s.get("vertical_down_m"),
                 s.get("max_altitude_m")),
            )

    # 7. Link scrobbles
    for s in day_data.scrobbles:
        cur.execute(
            """INSERT INTO music (entry_id, track, artist, album, played_at, source, scrobble_db_id)
               VALUES (%s, %s, %s, %s, %s, 'scrobble', %s)
               ON CONFLICT (entry_id, scrobble_db_id) WHERE scrobble_db_id IS NOT NULL
               DO NOTHING""",
            (entry_id, s["track"], s["artist"], s.get("album"), s.get("listened_at"), s["id"]),
        )

    # 7b. Backfill MBIDs from enrichment link table
    if settings.scrobble_db_password and day_data.scrobbles:
        from src.services.daily_summary import _backfill_mbids
        scrobble_dsn = settings.cross_dsn(
            settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password
        )
        _backfill_mbids(conn, scrobble_dsn, entry_id)

    # 8. Link watches
    for w in day_data.watches:
        session_key = str(w.get("reference_id", "")) if w.get("reference_id") else None
        watched_at = datetime.fromtimestamp(w["watched_at"], tz=timezone.utc) if w.get("watched_at") else None
        cur.execute(
            """INSERT INTO media_watch (entry_id, title, media_type, series_title,
                                        season, episode, platform, tautulli_session_key, watched_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (entry_id, tautulli_session_key)
                   WHERE tautulli_session_key IS NOT NULL
               DO NOTHING""",
            (entry_id, w["title"], w["media_type"], w.get("series_title"),
             w.get("season"), w.get("episode"), w.get("platform"),
             session_key, watched_at),
        )

    # 9. Link photos (reference only — served via Immich thumbnail proxy)
    if not skip_photos and day_data.photos:
        selected = select_representative_photos(day_data.photos, max_photos)
        for asset in selected:
            asset_id = asset.get("id")
            if not asset_id:
                continue
            att_uuid = str(uuid_mod.uuid4()).upper()
            exif = asset.get("exifInfo", {})
            original_name = asset.get("originalFileName", "")
            ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "jpeg"
            if ext == "jpg":
                ext = "jpeg"
            if ext == "heic":
                ext = "jpeg"  # treat HEIC as jpeg for type purposes
            cur.execute(
                """INSERT INTO attachment
                   (entry_id, uuid, type, filename, width, height,
                    camera_make, camera_model, lens_model, iso, f_number,
                    focal_length, date, immich_asset_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (entry_id, att_uuid, ext, original_name,
                 exif.get("exifImageWidth"), exif.get("exifImageHeight"),
                 exif.get("make"), exif.get("model"), exif.get("lensModel"),
                 exif.get("iso"), str(exif["fNumber"]) if exif.get("fNumber") else None,
                 str(exif["focalLength"]) if exif.get("focalLength") else None,
                 asset.get("fileCreatedAt"), asset_id),
            )

    # 10. Tag as 'retrospective'
    cur.execute(
        "INSERT INTO tag (name) VALUES ('retrospective') ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id"
    )
    tag_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO entry_tag (entry_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (entry_id, tag_id),
    )

    conn.commit()
    return entry_id
