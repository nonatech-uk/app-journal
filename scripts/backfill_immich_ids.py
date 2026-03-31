#!/usr/bin/env python3
"""Backfill attachment.immich_asset_id by matching filename and date against Immich.

Usage:
    python scripts/backfill_immich_ids.py [--dry-run] [--batch-size N] [--tolerance SECS]
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so we can import config.settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2
import psycopg2.extras

from config.settings import settings

MEDIA_TYPES_TO_SEARCH = {"jpeg", "png", "mov", "mp4"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill immich_asset_id on attachments")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without updating DB")
    parser.add_argument("--batch-size", type=int, default=100, help="Rows per batch (default: 100)")
    parser.add_argument("--tolerance", type=int, default=60, help="Date match tolerance in seconds (default: 60)")
    parser.add_argument("--immich-url", type=str, default=None, help="Override Immich URL (e.g. http://127.0.0.1:2283)")
    return parser.parse_args()


def immich_headers() -> dict:
    return {"x-api-key": settings.immich_api_key, "Accept": "application/json"}


def search_by_filename(client: httpx.Client, filename: str) -> list[dict]:
    """Search Immich for assets matching originalFileName."""
    # Strip extension for the search — Immich stores originalFileName without path
    resp = client.post(
        f"{settings.immich_url}/api/search/metadata",
        json={"originalFileName": filename},
        headers=immich_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("assets", {}).get("items", [])


def parse_dt(dt_str: str | None) -> datetime | None:
    """Parse an ISO datetime string to a timezone-aware datetime."""
    if not dt_str:
        return None
    # Handle various ISO formats from Immich
    s = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def dates_close(dt1: datetime | None, dt2: datetime | None, tolerance_secs: int) -> bool:
    """Return True if two datetimes are within tolerance_secs of each other."""
    if dt1 is None or dt2 is None:
        return False
    # Ensure both are aware
    if dt1.tzinfo is None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    if dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    return abs((dt1 - dt2).total_seconds()) <= tolerance_secs


def main() -> None:
    args = parse_args()

    if not settings.immich_api_key:
        print("ERROR: immich_api_key not configured. Set it in config/.env")
        sys.exit(1)

    if args.immich_url:
        settings.immich_url = args.immich_url

    print(f"Immich URL: {settings.immich_url}")
    print(f"Dry run: {args.dry_run}")
    print(f"Batch size: {args.batch_size}")
    print(f"Date tolerance: {args.tolerance}s")
    print()

    conn = psycopg2.connect(settings.dsn)
    conn.autocommit = False

    # Count total to process
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM attachment WHERE immich_asset_id IS NULL AND filename IS NOT NULL"
        )
        total = cur.fetchone()[0]

    print(f"Attachments to process: {total}")
    print()

    stats = {"matched_both": 0, "matched_filename_only": 0, "matched_date_only": 0, "skipped_no_filename": 0,
             "skipped_no_match": 0, "skipped_type": 0, "errors": 0, "processed": 0}

    client = httpx.Client()
    last_id = 0

    try:
        while True:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    """SELECT id, filename, date, type
                       FROM attachment
                       WHERE immich_asset_id IS NULL AND filename IS NOT NULL
                         AND id > %s
                       ORDER BY id
                       LIMIT %s""",
                    (last_id, args.batch_size),
                )
                rows = cur.fetchall()

            if not rows:
                break

            last_id = rows[-1]["id"]
            updates = []  # list of (immich_asset_id, attachment_id)

            for row in rows:
                att_id = row["id"]
                filename = row["filename"]
                att_date = row["date"]
                att_type = row["type"]
                stats["processed"] += 1

                # Skip types that won't be in Immich (pdf, audio)
                if att_type and att_type.lower() not in MEDIA_TYPES_TO_SEARCH:
                    stats["skipped_type"] += 1
                    continue

                if not filename:
                    stats["skipped_no_filename"] += 1
                    continue

                try:
                    assets = search_by_filename(client, filename)
                except Exception as e:
                    print(f"  ERROR searching for attachment {att_id} ({filename}): {e}")
                    stats["errors"] += 1
                    continue

                if not assets:
                    stats["skipped_no_match"] += 1
                    continue

                # Try to find the best match
                best_match = None
                best_quality = 0  # 0=none, 1=filename-only, 2=date-only, 3=both

                for asset in assets:
                    asset_filename = asset.get("originalFileName", "")
                    asset_date = parse_dt(asset.get("fileCreatedAt"))
                    # Filename already matched via search, but verify exact match
                    fn_match = (asset_filename == filename)
                    dt_match = dates_close(att_date, asset_date, args.tolerance)

                    if fn_match and dt_match:
                        quality = 3
                    elif fn_match:
                        quality = 2
                    elif dt_match:
                        quality = 1
                    else:
                        quality = 0

                    if quality > best_quality:
                        best_quality = quality
                        best_match = asset

                if best_match is None or best_quality == 0:
                    stats["skipped_no_match"] += 1
                    continue

                asset_id = best_match["id"]
                match_type = {3: "filename+date", 2: "filename_only", 1: "date_only"}[best_quality]

                if best_quality == 3:
                    stats["matched_both"] += 1
                elif best_quality == 2:
                    stats["matched_filename_only"] += 1
                else:
                    stats["matched_date_only"] += 1

                if args.dry_run:
                    print(f"  [DRY RUN] attachment {att_id} ({filename}) -> {asset_id} ({match_type})")
                else:
                    updates.append((asset_id, att_id))

                if best_quality < 3:
                    print(f"  WARN: attachment {att_id} ({filename}) matched {match_type} -> {asset_id}")

            # Apply updates for this batch
            if updates and not args.dry_run:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_batch(
                        cur,
                        "UPDATE attachment SET immich_asset_id = %s WHERE id = %s",
                        updates,
                    )
                conn.commit()
                print(f"  Committed {len(updates)} updates (up to id {last_id})")
            elif not args.dry_run:
                conn.commit()  # release any locks

            # Progress
            done = stats["processed"]
            matched = stats["matched_both"] + stats["matched_filename_only"] + stats["matched_date_only"]
            print(f"  Progress: {done}/{total} processed, {matched} matched so far")

    except KeyboardInterrupt:
        print("\nInterrupted. Rolling back current batch.")
        conn.rollback()
    finally:
        client.close()
        conn.close()

    # Summary
    print()
    print("=== Summary ===")
    print(f"  Total processed:       {stats['processed']}")
    print(f"  Matched (both):        {stats['matched_both']}")
    print(f"  Matched (filename):    {stats['matched_filename_only']}")
    print(f"  Matched (date only):   {stats['matched_date_only']}")
    total_matched = stats["matched_both"] + stats["matched_filename_only"] + stats["matched_date_only"]
    print(f"  Total matched:         {total_matched}")
    print(f"  Skipped (no match):    {stats['skipped_no_match']}")
    print(f"  Skipped (type):        {stats['skipped_type']}")
    print(f"  Skipped (no filename): {stats['skipped_no_filename']}")
    print(f"  Errors:                {stats['errors']}")


if __name__ == "__main__":
    main()
