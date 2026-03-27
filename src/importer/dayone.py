"""Import DayOne SQLite data into PostgreSQL journal database."""

import argparse
import plistlib
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

# Mac Cocoa epoch: 2001-01-01 00:00:00 UTC
COCOA_EPOCH = 978307200


def cocoa_to_utc(ts):
    """Convert Cocoa timestamp (seconds since 2001-01-01) to UTC datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts + COCOA_EPOCH, tz=timezone.utc)


def decode_timezone(blob):
    """Extract IANA timezone name from NSKeyedArchiver plist blob."""
    if not blob:
        return None
    try:
        obj = plistlib.loads(blob)
        objects = obj.get("$objects", [])
        # The timezone name is typically at index 2 in the $objects array
        for item in objects:
            if isinstance(item, str) and "/" in item:
                return item
        return None
    except Exception:
        return None


def import_dayone(sqlite_path: str, pg_dsn: str, media_src: str, media_dest: str):
    """Run the full import from DayOne SQLite to PostgreSQL."""
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    pg = psycopg2.connect(pg_dsn)
    pg.autocommit = False
    cur = pg.cursor()

    media_src_path = Path(media_src)
    media_dest_path = Path(media_dest)

    # ── Journals ──────────────────────────────────────────────────────────
    print("Importing journals...")
    rows = src.execute(
        "SELECT Z_PK, ZNAME, ZCOLORHEX, ZJOURNALDESCRIPTION, ZISTRASHJOURNAL FROM ZJOURNAL"
    ).fetchall()
    journal_map = {}  # dayone_pk -> pg_id
    for r in rows:
        cur.execute(
            """INSERT INTO journal (dayone_pk, name, color_hex, description, is_trash)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (dayone_pk) DO UPDATE SET name = EXCLUDED.name
               RETURNING id""",
            (r["Z_PK"], r["ZNAME"] or "Untitled", r["ZCOLORHEX"], r["ZJOURNALDESCRIPTION"],
             bool(r["ZISTRASHJOURNAL"])),
        )
        journal_map[r["Z_PK"]] = cur.fetchone()[0]
    print(f"  {len(journal_map)} journals")

    # ── Tags ──────────────────────────────────────────────────────────────
    print("Importing tags...")
    rows = src.execute("SELECT Z_PK, ZNAME FROM ZTAG").fetchall()
    tag_map = {}  # dayone_pk -> pg_id
    for r in rows:
        if not r["ZNAME"]:
            continue
        cur.execute(
            """INSERT INTO tag (name) VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
               RETURNING id""",
            (r["ZNAME"],),
        )
        tag_map[r["Z_PK"]] = cur.fetchone()[0]
    print(f"  {len(tag_map)} tags")

    # ── Entries ────────────────────────────────────────────────────────────
    print("Importing entries...")
    rows = src.execute("""
        SELECT Z_PK, ZUUID, ZJOURNAL, ZCREATIONDATE, ZMODIFIEDDATE,
               ZMARKDOWNTEXT, ZRICHTEXTJSON, ZSTARRED, ZISPINNED, ZISDRAFT,
               ZISALLDAY, ZDURATION, ZCREATIONDEVICE, ZCREATIONDEVICEMODEL,
               ZCREATIONDEVICETYPE, ZTIMEZONE,
               ZGREGORIANYEAR, ZGREGORIANMONTH, ZGREGORIANDAY
        FROM ZENTRY
        ORDER BY ZCREATIONDATE
    """).fetchall()

    entry_map = {}  # dayone_pk -> pg_id
    for r in rows:
        tz_name = decode_timezone(r["ZTIMEZONE"])
        journal_id = journal_map.get(r["ZJOURNAL"])
        cur.execute(
            """INSERT INTO entry (uuid, journal_id, created_at, modified_at,
                   markdown_text, rich_text_json, starred, pinned, is_draft,
                   is_all_day, duration, device_name, device_model, device_type,
                   timezone, gregorian_year, gregorian_month, gregorian_day)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (uuid) DO UPDATE SET modified_at = EXCLUDED.modified_at
               RETURNING id""",
            (
                r["ZUUID"], journal_id,
                cocoa_to_utc(r["ZCREATIONDATE"]),
                cocoa_to_utc(r["ZMODIFIEDDATE"]),
                r["ZMARKDOWNTEXT"],
                r["ZRICHTEXTJSON"],
                bool(r["ZSTARRED"]),
                bool(r["ZISPINNED"]),
                bool(r["ZISDRAFT"]),
                bool(r["ZISALLDAY"]),
                r["ZDURATION"] or 0,
                r["ZCREATIONDEVICE"],
                r["ZCREATIONDEVICEMODEL"],
                r["ZCREATIONDEVICETYPE"],
                tz_name,
                r["ZGREGORIANYEAR"],
                r["ZGREGORIANMONTH"],
                r["ZGREGORIANDAY"],
            ),
        )
        entry_map[r["Z_PK"]] = cur.fetchone()[0]

    print(f"  {len(entry_map)} entries")

    # ── Entry-Tag join ────────────────────────────────────────────────────
    print("Importing entry-tag associations...")
    rows = src.execute("SELECT Z_17ENTRIES, Z_65TAGS1 FROM Z_17TAGS").fetchall()
    count = 0
    for r in rows:
        entry_id = entry_map.get(r["Z_17ENTRIES"])
        tag_id = tag_map.get(r["Z_65TAGS1"])
        if entry_id and tag_id:
            cur.execute(
                """INSERT INTO entry_tag (entry_id, tag_id) VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (entry_id, tag_id),
            )
            count += 1
    print(f"  {count} associations")

    # ── Locations ─────────────────────────────────────────────────────────
    print("Importing locations...")
    rows = src.execute("""
        SELECT l.Z_PK, e.Z_PK as entry_pk,
               l.ZLATITUDE, l.ZLONGITUDE, l.ZALTITUDE, l.ZHEADING, l.ZSPEED,
               l.ZPLACENAME, l.ZADDRESS, l.ZLOCALITYNAME,
               l.ZADMINISTRATIVEAREA, l.ZCOUNTRY, l.ZTIMEZONENAME, l.ZUSERLABEL
        FROM ZLOCATION l
        JOIN ZENTRY e ON e.ZLOCATION = l.Z_PK
    """).fetchall()
    count = 0
    for r in rows:
        entry_id = entry_map.get(r["entry_pk"])
        if not entry_id:
            continue
        cur.execute(
            """INSERT INTO location (entry_id, latitude, longitude, altitude,
                   heading, speed, place_name, address, locality,
                   admin_area, country, timezone_name, user_label)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (entry_id) DO NOTHING""",
            (
                entry_id, r["ZLATITUDE"], r["ZLONGITUDE"], r["ZALTITUDE"],
                r["ZHEADING"], r["ZSPEED"],
                r["ZPLACENAME"], r["ZADDRESS"], r["ZLOCALITYNAME"],
                r["ZADMINISTRATIVEAREA"], r["ZCOUNTRY"],
                r["ZTIMEZONENAME"], r["ZUSERLABEL"],
            ),
        )
        count += 1
    print(f"  {count} locations")

    # ── Weather ───────────────────────────────────────────────────────────
    print("Importing weather...")
    rows = src.execute("""
        SELECT w.Z_PK, e.Z_PK as entry_pk,
               w.ZTEMPERATURECELSIUS, w.ZCONDITIONSDESCRIPTION, w.ZWEATHERCODE,
               w.ZRELATIVEHUMIDITY, w.ZWINDSPEEDKPH, w.ZWINDBEARING,
               w.ZWINDCHILLCELSIUS, w.ZPRESSUREMB, w.ZVISIBILITYKM,
               w.ZMOONPHASE, w.ZMOONPHASECODE,
               w.ZSUNRISEDATE, w.ZSUNSETDATE
        FROM ZWEATHER w
        JOIN ZENTRY e ON e.ZWEATHER = w.Z_PK
    """).fetchall()
    count = 0
    for r in rows:
        entry_id = entry_map.get(r["entry_pk"])
        if not entry_id:
            continue
        cur.execute(
            """INSERT INTO weather (entry_id, temp_celsius, conditions, weather_code,
                   relative_humidity, wind_speed_kph, wind_bearing,
                   wind_chill_celsius, pressure_mb, visibility_km,
                   moon_phase, moon_phase_code, sunrise, sunset)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (entry_id) DO NOTHING""",
            (
                entry_id, r["ZTEMPERATURECELSIUS"], r["ZCONDITIONSDESCRIPTION"],
                r["ZWEATHERCODE"], r["ZRELATIVEHUMIDITY"],
                r["ZWINDSPEEDKPH"], r["ZWINDBEARING"],
                r["ZWINDCHILLCELSIUS"], r["ZPRESSUREMB"], r["ZVISIBILITYKM"],
                r["ZMOONPHASE"], r["ZMOONPHASECODE"],
                cocoa_to_utc(r["ZSUNRISEDATE"]),
                cocoa_to_utc(r["ZSUNSETDATE"]),
            ),
        )
        count += 1
    print(f"  {count} weather records")

    # ── Music ─────────────────────────────────────────────────────────────
    print("Importing music...")
    rows = src.execute("""
        SELECT m.Z_PK, m.ZENTRY as entry_pk,
               m.ZTRACK, m.ZARTIST, m.ZALBUM, m.ZALBUMYEAR
        FROM ZMUSIC m
    """).fetchall()
    count = 0
    for r in rows:
        entry_id = entry_map.get(r["entry_pk"])
        if not entry_id:
            continue
        cur.execute(
            """INSERT INTO music (entry_id, track, artist, album, album_year)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (entry_id) DO NOTHING""",
            (entry_id, r["ZTRACK"], r["ZARTIST"], r["ZALBUM"], r["ZALBUMYEAR"]),
        )
        count += 1
    print(f"  {count} music records")

    # ── Attachments ───────────────────────────────────────────────────────
    print("Importing attachments and copying media...")
    rows = src.execute("""
        SELECT Z_PK, ZENTRY, ZIDENTIFIER, ZTYPE, ZFILENAME, ZFILESIZE,
               ZWIDTH, ZHEIGHT, ZORDERINENTRY, ZCAPTION, ZDURATION,
               ZFAVORITE, ZCAMERAMAKE, ZCAMERAMODEL, ZLENSMODEL,
               ZISO, ZFNUMBER, ZFOCALLENGTH, ZTRANSCRIPTION, ZDATE
        FROM ZATTACHMENT
    """).fetchall()
    count = 0
    skipped = 0
    for r in rows:
        entry_id = entry_map.get(r["ZENTRY"])
        if not entry_id:
            skipped += 1
            continue

        att_type = r["ZTYPE"] or "jpeg"
        identifier = r["ZIDENTIFIER"] or ""

        # Determine source file path
        type_dirs = {
            "jpeg": "DayOnePhotos",
            "png": "DayOnePhotos",
            "mov": "DayOneVideos",
            "mp4": "DayOneVideos",
            "pdf": "DayOnePDFAttachments",
        }
        src_dir = type_dirs.get(att_type, "DayOnePhotos")
        ext = att_type if att_type != "jpeg" else "jpeg"
        src_file = media_src_path / src_dir / f"{identifier.lower()}.{ext}"

        # Destination: type_dir/identifier.ext
        local_path = f"{src_dir}/{identifier.lower()}.{ext}"
        dest_file = media_dest_path / local_path

        # Copy file if it exists
        if src_file.exists():
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if not dest_file.exists():
                shutil.copy2(src_file, dest_file)
        else:
            # Try without extension matching — some files have different extensions
            found = False
            for f in media_src_path.glob(f"{src_dir}/{identifier.lower()}.*"):
                actual_ext = f.suffix.lstrip(".")
                local_path = f"{src_dir}/{identifier.lower()}.{actual_ext}"
                dest_file = media_dest_path / local_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if not dest_file.exists():
                    shutil.copy2(f, dest_file)
                found = True
                break
            if not found:
                local_path = None

        cur.execute(
            """INSERT INTO attachment (entry_id, uuid, type, filename, file_size,
                   width, height, order_in_entry, caption, duration,
                   is_favorite, camera_make, camera_model, lens_model,
                   iso, f_number, focal_length, transcription, date, local_path)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                entry_id, identifier, att_type,
                r["ZFILENAME"], r["ZFILESIZE"],
                r["ZWIDTH"], r["ZHEIGHT"],
                r["ZORDERINENTRY"] or 0,
                r["ZCAPTION"], r["ZDURATION"],
                bool(r["ZFAVORITE"]),
                r["ZCAMERAMAKE"], r["ZCAMERAMODEL"], r["ZLENSMODEL"],
                r["ZISO"], r["ZFNUMBER"], r["ZFOCALLENGTH"],
                r["ZTRANSCRIPTION"],
                cocoa_to_utc(r["ZDATE"]),
                local_path,
            ),
        )
        count += 1

    print(f"  {count} attachments ({skipped} skipped — no matching entry)")

    pg.commit()
    cur.close()
    pg.close()
    src.close()
    print("Import complete.")


def main():
    parser = argparse.ArgumentParser(description="Import DayOne data to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="Path to DayOne.sqlite")
    parser.add_argument("--dsn", required=True, help="PostgreSQL DSN")
    parser.add_argument("--media-src", required=True, help="Path to DayOne Documents dir")
    parser.add_argument("--media-dest", required=True, help="Destination for media files")
    args = parser.parse_args()
    import_dayone(args.sqlite, args.dsn, args.media_src, args.media_dest)


if __name__ == "__main__":
    main()
