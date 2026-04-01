import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from fastapi.responses import Response

from config.settings import settings
from src.api.deps import get_conn, get_current_user, require_admin
from src.api.models import (
    AttachmentOut,
    ChildEntrySummary,
    EntryCreate,
    EntryDetail,
    EntryList,
    EntrySummary,
    EntryUpdate,
    ImmichAttachRequest,
    LocationOut,
    MusicOut,
    MusicTrackOut,
    WeatherOut,
)

router = APIRouter()

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _create_daily_summary(cur, year: int, month: int, day: int, tz: str | None) -> int:
    """Create a daily_summary entry for the given date. Returns the new entry ID.

    Uses INSERT ... ON CONFLICT to handle concurrent requests safely.
    """
    entry_uuid = str(uuid.uuid4()).upper()
    title = f"## {day} {MONTH_NAMES[month]} {year}"
    cur.execute(
        """INSERT INTO entry (uuid, created_at, modified_at, markdown_text,
                              entry_type, is_all_day, timezone,
                              gregorian_year, gregorian_month, gregorian_day)
           VALUES (%s, make_date(%s, %s, %s)::timestamptz, now(), %s,
                   'daily_summary', true, %s, %s, %s, %s)
           ON CONFLICT (gregorian_year, gregorian_month, gregorian_day)
               WHERE entry_type = 'daily_summary'
           DO NOTHING
           RETURNING id""",
        (entry_uuid, year, month, day, title, tz, year, month, day),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    # Concurrent insert won — fetch the existing summary
    cur.execute(
        """SELECT id FROM entry
           WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
             AND entry_type = 'daily_summary'""",
        (year, month, day),
    )
    return cur.fetchone()[0]


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
            place_id=row[14], place_label=row[15],
        )

    # Weather
    weather = None
    if row[16] is not None:
        weather = WeatherOut(temp_celsius=row[16], conditions=row[17], weather_code=row[18])

    # Music
    music = None
    if row[19]:
        music = MusicOut(track=row[19], artist=row[20], album=row[21])

    return EntrySummary(
        id=entry_id,
        uuid=row[1],
        journal_id=row[2],
        journal_name=row[3],
        created_at=row[4],
        starred=row[5],
        pinned=row[7],
        entry_type=row[22] if len(row) > 22 else "diary",
        parent_entry_id=row[23] if len(row) > 23 else None,
        child_count=row[24] if len(row) > 24 else 0,
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
    entry_type: str | None = Query(None),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    conditions = ["e.entry_type != 'daily_summary'"]
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
    if entry_type:
        # Override the default daily_summary filter when explicitly requested
        conditions = [c for c in conditions if "daily_summary" not in c]
        conditions.append("e.entry_type = %(entry_type)s")
        params["entry_type"] = entry_type

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    cur.execute(f"""
        SELECT e.id, e.uuid, e.journal_id, j.name,
               e.created_at, e.starred, e.markdown_text, e.pinned,
               l.latitude, l.longitude, l.place_name, l.locality,
               l.admin_area, l.country, l.place_id, l.place_label,
               w.temp_celsius, w.conditions, w.weather_code,
               m.track, m.artist, m.album,
               e.entry_type, e.parent_entry_id,
               (SELECT count(*) FROM entry c WHERE c.parent_entry_id = e.id) AS child_count
        FROM entry e
        LEFT JOIN journal j ON j.id = e.journal_id
        LEFT JOIN LATERAL (
            SELECT * FROM location WHERE entry_id = e.id
            ORDER BY CASE WHEN location_type = 'primary' THEN 0 ELSE 1 END, sequence_order
            LIMIT 1
        ) l ON true
        LEFT JOIN LATERAL (
            SELECT * FROM weather WHERE entry_id = e.id
            ORDER BY sequence_order DESC
            LIMIT 1
        ) w ON true
        LEFT JOIN LATERAL (
            SELECT * FROM music WHERE entry_id = e.id
            ORDER BY CASE WHEN source = 'dayone' THEN 0 ELSE 1 END, played_at DESC NULLS LAST
            LIMIT 1
        ) m ON true
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
               e.device_name, e.device_model, e.timezone,
               e.retrospective, e.retrospective_at,
               e.entry_type, e.mood, e.energy, e.parent_entry_id
        FROM entry e
        LEFT JOIN journal j ON j.id = e.journal_id
        WHERE e.id = %s
    """, (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")

    # Locations (all, ordered primary first)
    cur.execute("SELECT latitude, longitude, altitude, place_name, address, locality, admin_area, country, place_id, place_label, location_type FROM location WHERE entry_id = %s ORDER BY CASE WHEN location_type = 'primary' THEN 0 ELSE 1 END, sequence_order", (entry_id,))
    loc_rows = cur.fetchall()
    locations = [
        LocationOut(latitude=r[0], longitude=r[1], altitude=r[2], place_name=r[3], address=r[4], locality=r[5], admin_area=r[6], country=r[7], place_id=r[8], place_label=r[9], location_type=r[10])
        for r in loc_rows
    ]
    loc = locations[0] if locations else None

    # Weather (all records, ordered by sequence)
    cur.execute("SELECT temp_celsius, conditions, weather_code, relative_humidity, wind_speed_kph, pressure_mb, visibility_km, moon_phase, sunrise, sunset, location_id FROM weather WHERE entry_id = %s ORDER BY sequence_order", (entry_id,))
    w_rows = cur.fetchall()
    weathers = [
        WeatherOut(temp_celsius=r[0], conditions=r[1], weather_code=r[2], relative_humidity=r[3], wind_speed_kph=r[4], pressure_mb=r[5], visibility_km=r[6], moon_phase=r[7], sunrise=r[8], sunset=r[9], location_id=r[10])
        for r in w_rows
    ]
    weather = weathers[-1] if weathers else None  # last weather for backward compat

    # Music (Day One entries first, then most recent scrobble)
    cur.execute("SELECT track, artist, album, album_year FROM music WHERE entry_id = %s ORDER BY CASE WHEN source = 'dayone' THEN 0 ELSE 1 END, played_at DESC NULLS LAST LIMIT 1", (entry_id,))
    m_row = cur.fetchone()
    music = MusicOut(track=m_row[0], artist=m_row[1], album=m_row[2], album_year=m_row[3]) if m_row else None

    # All music tracks with enrichment data
    cur.execute("""
        SELECT track, artist, album, album_year, played_at, source,
               recording_mbid::text, artist_mbid::text, spotify_track_id
        FROM music WHERE entry_id = %s
        ORDER BY played_at ASC NULLS LAST, id
    """, (entry_id,))
    music_tracks = [
        MusicTrackOut(
            track=r[0], artist=r[1], album=r[2], album_year=r[3],
            played_at=r[4], source=r[5],
            recording_mbid=r[6], artist_mbid=r[7],
            spotify_track_id=r[8],
        )
        for r in cur.fetchall()
    ]

    # Tags
    cur.execute("SELECT t.name FROM entry_tag et JOIN tag t ON t.id = et.tag_id WHERE et.entry_id = %s", (entry_id,))
    tags = [r[0] for r in cur.fetchall()]

    # Attachments
    cur.execute("""
        SELECT id, uuid, type, filename, width, height, caption, duration,
               is_favorite, camera_make, camera_model, date, immich_asset_id
        FROM attachment WHERE entry_id = %s ORDER BY order_in_entry, id
    """, (entry_id,))
    attachments = [
        AttachmentOut(
            id=a[0], uuid=a[1], type=a[2], filename=a[3],
            width=a[4], height=a[5], caption=a[6], duration=a[7],
            is_favorite=a[8], camera_make=a[9], camera_model=a[10],
            date=a[11], media_url=f"/api/v1/media/{a[0]}",
            immich_asset_id=a[12],
            immich_url=f"{settings.immich_public_url}/photos/{a[12]}" if a[12] else None,
        )
        for a in cur.fetchall()
    ]

    rich_text = None
    if row[7]:
        try:
            rich_text = json.loads(row[7]) if isinstance(row[7], str) else row[7]
        except (json.JSONDecodeError, TypeError):
            pass

    # Children (for daily_summary entries)
    children = []
    if row[18] == "daily_summary":
        cur.execute("""
            SELECT e.id, e.uuid, e.created_at, left(e.markdown_text, 200),
                   e.mood, e.energy,
                   (SELECT count(*) FROM attachment a WHERE a.entry_id = e.id)
            FROM entry e
            WHERE e.parent_entry_id = %s
            ORDER BY e.created_at
        """, (entry_id,))
        for c in cur.fetchall():
            text = (c[3] or "").replace("\n", " ").strip() or None
            children.append(ChildEntrySummary(
                id=c[0], uuid=c[1], created_at=c[2],
                text_preview=text, mood=c[4], energy=c[5],
                attachment_count=c[6],
            ))

    # Adjacent entries (prev/next by date, parent-level only)
    created_at = row[4]
    cur.execute(
        "SELECT id FROM entry WHERE created_at < %s AND parent_entry_id IS NULL ORDER BY created_at DESC LIMIT 1",
        (created_at,),
    )
    prev_row = cur.fetchone()
    cur.execute(
        "SELECT id FROM entry WHERE created_at > %s AND parent_entry_id IS NULL ORDER BY created_at ASC LIMIT 1",
        (created_at,),
    )
    next_row = cur.fetchone()

    return EntryDetail(
        id=row[0], uuid=row[1], journal_id=row[2], journal_name=row[3],
        created_at=created_at, modified_at=row[5],
        markdown_text=row[6], rich_text_json=rich_text,
        starred=row[8], pinned=row[9], is_draft=row[10],
        is_all_day=row[11], duration=row[12],
        device_name=row[13], device_model=row[14], timezone=row[15],
        retrospective=row[16], retrospective_at=row[17],
        entry_type=row[18], mood=row[19], energy=row[20],
        parent_entry_id=row[21],
        prev_entry_id=prev_row[0] if prev_row else None,
        next_entry_id=next_row[0] if next_row else None,
        location=loc, locations=locations, weather=weather, weathers=weathers, music=music, music_tracks=music_tracks,
        tags=tags, attachments=attachments, children=children,
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


@router.put("/entries/{entry_id}", response_model=EntryDetail)
def update_entry(
    entry_id: int,
    body: EntryUpdate,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()

    # Check entry exists
    cur.execute("SELECT id FROM entry WHERE id = %s", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")

    if body.markdown_text is not None:
        cur.execute(
            """UPDATE entry
               SET markdown_text = %s,
                   modified_at = now(),
                   search_vector = to_tsvector('english', %s)
               WHERE id = %s""",
            (body.markdown_text, body.markdown_text, entry_id),
        )

    if body.retrospective is not None:
        cur.execute(
            """UPDATE entry
               SET retrospective = %s, retrospective_at = now(), modified_at = now()
               WHERE id = %s""",
            (body.retrospective, entry_id),
        )

    if body.mood is not None:
        cur.execute("UPDATE entry SET mood = %s, modified_at = now() WHERE id = %s", (body.mood if body.mood > 0 else None, entry_id))

    if body.energy is not None:
        cur.execute("UPDATE entry SET energy = %s, modified_at = now() WHERE id = %s", (body.energy if body.energy > 0 else None, entry_id))

    if body.tags is not None:
        cur.execute("DELETE FROM entry_tag WHERE entry_id = %s", (entry_id,))
        for tag_name in body.tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            cur.execute(
                "INSERT INTO tag (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
                (tag_name,),
            )
            tag_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO entry_tag (entry_id, tag_id) VALUES (%s, %s)",
                (entry_id, tag_id),
            )

    conn.commit()
    return get_entry(entry_id, conn=conn, _user=_user)


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("DELETE FROM entry WHERE id = %s RETURNING id", (entry_id,))
    if not cur.fetchone():
        raise HTTPException(404, "Entry not found")
    conn.commit()
    return Response(status_code=204)


@router.post("/entries", response_model=EntryDetail)
def create_entry(
    body: EntryCreate,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    entry_uuid = str(uuid.uuid4()).upper()
    now = datetime.now(timezone.utc)

    # Insert entry
    retro_at = now if body.retrospective else None
    cur.execute(
        """INSERT INTO entry (uuid, journal_id, created_at, modified_at,
                              markdown_text, starred, timezone,
                              retrospective, retrospective_at,
                              gregorian_year, gregorian_month, gregorian_day)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (
            entry_uuid, body.journal_id, now, now,
            body.markdown_text, body.starred, body.timezone,
            body.retrospective, retro_at,
            now.year, now.month, now.day,
        ),
    )
    entry_id = cur.fetchone()[0]

    # Daily summary: check if this day already has entries
    cur.execute(
        """SELECT id FROM entry
           WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
             AND entry_type = 'daily_summary'""",
        (now.year, now.month, now.day),
    )
    summary_row = cur.fetchone()
    if summary_row:
        # Summary already exists — set parent on new entry
        cur.execute(
            "UPDATE entry SET parent_entry_id = %s WHERE id = %s",
            (summary_row[0], entry_id),
        )
    else:
        # Check for existing diary entries on this day (excluding the one just created)
        cur.execute(
            """SELECT id FROM entry
               WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
                 AND id != %s AND entry_type != 'daily_summary'""",
            (now.year, now.month, now.day, entry_id),
        )
        siblings = cur.fetchall()
        if siblings:
            # Second+ entry for the day — create summary, reparent all
            summary_id = _create_daily_summary(cur, now.year, now.month, now.day, body.timezone)
            cur.execute(
                """UPDATE entry SET parent_entry_id = %s
                   WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
                     AND entry_type != 'daily_summary'""",
                (summary_id, now.year, now.month, now.day),
            )

    # Location
    if body.location:
        loc = body.location
        cur.execute(
            """INSERT INTO location (entry_id, latitude, longitude, altitude,
                                     place_name, address, locality, admin_area, country)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                entry_id, loc.latitude, loc.longitude, loc.altitude,
                loc.place_name, loc.address, loc.locality, loc.admin_area, loc.country,
            ),
        )

    # Weather
    if body.weather:
        w = body.weather
        cur.execute(
            """INSERT INTO weather (entry_id, temp_celsius, conditions, weather_code,
                                    relative_humidity, wind_speed_kph, wind_bearing,
                                    pressure_mb, visibility_km)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                entry_id, w.temp_celsius, w.conditions, w.weather_code,
                w.relative_humidity, w.wind_speed_kph, w.wind_bearing,
                w.pressure_mb, w.visibility_km,
            ),
        )

    # Music
    if body.music:
        m = body.music
        cur.execute(
            """INSERT INTO music (entry_id, track, artist, album, album_year)
               VALUES (%s, %s, %s, %s, %s)""",
            (entry_id, m.track, m.artist, m.album, m.album_year),
        )

    # Tags
    for tag_name in body.tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        cur.execute(
            "INSERT INTO tag (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (tag_name,),
        )
        tag_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO entry_tag (entry_id, tag_id) VALUES (%s, %s)",
            (entry_id, tag_id),
        )

    # Immich assets
    if body.immich_asset_ids:
        from src.services.immich import download_asset

        for asset_id in body.immich_asset_ids:
            meta = download_asset(settings, asset_id, settings.media_root, entry_uuid)
            if meta:
                att_uuid = str(uuid.uuid4()).upper()
                cur.execute(
                    """INSERT INTO attachment
                       (entry_id, uuid, type, filename, file_size, width, height,
                        camera_make, camera_model, lens_model, iso, f_number,
                        focal_length, date, local_path, immich_asset_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        entry_id, att_uuid, meta["type"], meta["filename"],
                        meta["file_size"], meta["width"], meta["height"],
                        meta["camera_make"], meta["camera_model"], meta["lens_model"],
                        meta["iso"], meta["f_number"], meta["focal_length"],
                        meta["date"], meta["local_path"], meta["immich_asset_id"],
                    ),
                )

    conn.commit()
    return get_entry(entry_id, conn=conn, _user=_user)


@router.post("/entries/{entry_id}/voice", response_model=EntryDetail)
def upload_voice_note(
    entry_id: int,
    audio: UploadFile = File(...),
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Upload a voice note, transcribe it, and attach to an entry."""
    cur = conn.cursor()
    cur.execute("SELECT uuid FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")
    entry_uuid = row[0]

    # Save audio file
    entry_dir = Path(settings.media_root) / entry_uuid
    entry_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(audio.filename or "voice.webm").suffix or ".webm"
    voice_filename = f"voice_{int(datetime.now(timezone.utc).timestamp())}{ext}"
    voice_path = entry_dir / voice_filename
    content = audio.file.read()
    voice_path.write_bytes(content)

    # Transcribe
    transcription = None
    if settings.openai_api_key:
        from src.services.transcription import transcribe_audio
        transcription = transcribe_audio(str(voice_path), settings.openai_api_key)

    # Insert attachment
    att_uuid = str(uuid.uuid4()).upper()
    relative_path = f"{entry_uuid}/{voice_filename}"
    cur.execute(
        """INSERT INTO attachment
           (entry_id, uuid, type, filename, file_size, local_path, transcription)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            entry_id, att_uuid, "audio", voice_filename,
            len(content), relative_path, transcription,
        ),
    )

    # Append transcription to entry text if available
    if transcription:
        cur.execute(
            """UPDATE entry
               SET markdown_text = COALESCE(markdown_text, '') || %s,
                   modified_at = now()
               WHERE id = %s""",
            (f"\n\n---\n*Voice note:* {transcription}\n", entry_id),
        )

    conn.commit()
    return get_entry(entry_id, conn=conn, _user=_user)


@router.post("/entries/{entry_id}/attachments/immich", response_model=EntryDetail)
def attach_immich_photos(
    entry_id: int,
    body: ImmichAttachRequest,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Download photos from Immich and attach to an existing entry."""
    cur = conn.cursor()
    cur.execute("SELECT uuid FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")
    entry_uuid = row[0]

    from src.services.immich import download_asset

    for asset_id in body.immich_asset_ids:
        meta = download_asset(settings, asset_id, settings.media_root, entry_uuid)
        if meta:
            att_uuid = str(uuid.uuid4()).upper()
            cur.execute(
                """INSERT INTO attachment
                   (entry_id, uuid, type, filename, file_size, width, height,
                    camera_make, camera_model, lens_model, iso, f_number,
                    focal_length, date, local_path, immich_asset_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    entry_id, att_uuid, meta["type"], meta["filename"],
                    meta["file_size"], meta["width"], meta["height"],
                    meta["camera_make"], meta["camera_model"], meta["lens_model"],
                    meta["iso"], meta["f_number"], meta["focal_length"],
                    meta["date"], meta["local_path"], meta["immich_asset_id"],
                ),
            )

    conn.commit()
    return get_entry(entry_id, conn=conn, _user=_user)


@router.delete("/entries/{entry_id}/attachments/{attachment_id}")
def delete_attachment(
    entry_id: int,
    attachment_id: int,
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute(
        "SELECT local_path FROM attachment WHERE id = %s AND entry_id = %s",
        (attachment_id, entry_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Attachment not found")

    # Delete file from disk if it exists
    if row[0]:
        file_path = Path(settings.media_root) / row[0]
        if file_path.exists():
            file_path.unlink()

    cur.execute("DELETE FROM attachment WHERE id = %s", (attachment_id,))
    conn.commit()
    return {"deleted": True}


@router.post("/entries/{entry_id}/attachments/upload", response_model=EntryDetail)
def upload_attachment(
    entry_id: int,
    file: UploadFile = File(...),
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    cur = conn.cursor()
    cur.execute("SELECT uuid FROM entry WHERE id = %s", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Entry not found")
    entry_uuid = row[0]

    # Determine type from extension
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    type_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "png",
                "mov": "mov", "mp4": "mp4", "pdf": "pdf", "heic": "jpeg", "webp": "png"}
    media_type = type_map.get(ext, "jpeg")

    # Save file
    dest_dir = Path(settings.media_root) / entry_uuid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    content = file.file.read()
    dest_path.write_bytes(content)

    relative_path = f"{entry_uuid}/{filename}"
    file_size = len(content)

    # Extract dimensions for images
    width = None
    height = None
    if media_type in ("jpeg", "png"):
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(content))
            width, height = img.size
        except Exception:
            pass

    att_uuid = str(uuid.uuid4()).upper()
    cur.execute(
        """INSERT INTO attachment
           (entry_id, uuid, type, filename, file_size, width, height,
            local_path, order_in_entry)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                   (SELECT COALESCE(MAX(order_in_entry), 0) + 1 FROM attachment WHERE entry_id = %s))""",
        (entry_id, att_uuid, media_type, filename, file_size, width, height,
         relative_path, entry_id),
    )
    conn.commit()
    return get_entry(entry_id, conn=conn, _user=_user)
