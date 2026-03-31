#!/usr/bin/env python3
"""One-time migration: create daily_summary entries for historical multi-entry days.

Creates summaries for the ~802 days that have more than one diary/retrospective entry,
reparents child entries, consolidates structured data, and enriches from sources.

Usage:
    python scripts/migrate_daily_summaries.py --dry-run
    python scripts/migrate_daily_summaries.py
    python scripts/migrate_daily_summaries.py --start-date 2024-01-01 --end-date 2024-12-31
"""

import argparse
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from config.settings import settings
from src.services.daily_summary import consolidate_structured_data, enrich_from_sources

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate multi-entry days to daily summaries")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be created without writing")
    parser.add_argument("--start-date", type=str, default=None, help="Start of date range (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="End of date range (YYYY-MM-DD)")
    parser.add_argument("--batch-size", type=int, default=50, help="Commit every N days (default: 50)")
    parser.add_argument("--skip-enrichment", action="store_true", help="Skip Task B (source top-up)")
    parser.add_argument("--fix-trips", action="store_true", help="Fix trip_entry references to point to summaries")
    return parser.parse_args()


def find_multi_entry_days(cur, start_date=None, end_date=None):
    """Find all calendar days with more than one diary/retrospective entry."""
    conditions = ["entry_type IN ('diary', 'retrospective')", "parent_entry_id IS NULL"]
    params = []

    if start_date:
        conditions.append("make_date(gregorian_year, gregorian_month, gregorian_day) >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("make_date(gregorian_year, gregorian_month, gregorian_day) <= %s")
        params.append(end_date)

    where = " AND ".join(conditions)
    cur.execute(f"""
        SELECT gregorian_year, gregorian_month, gregorian_day,
               array_agg(id ORDER BY created_at) AS entry_ids,
               array_agg(left(markdown_text, 80) ORDER BY created_at) AS previews
        FROM entry
        WHERE {where}
        GROUP BY gregorian_year, gregorian_month, gregorian_day
        HAVING count(*) > 1
        ORDER BY gregorian_year, gregorian_month, gregorian_day
    """, params)
    return cur.fetchall()


def create_summary_entry(cur, year, month, day, child_ids, previews):
    """Create a daily_summary entry with stub markdown linking to children."""
    entry_uuid = str(uuid.uuid4()).upper()
    title = f"{day} {MONTH_NAMES[month]} {year}"

    # Build stub markdown with links to children
    lines = [f"## {title}", ""]
    for i, (child_id, preview) in enumerate(zip(child_ids, previews)):
        # Extract first line as title
        text = (preview or "").strip()
        first_line = text.split("\n")[0].lstrip("#").strip() if text else f"Entry {i + 1}"
        if not first_line:
            first_line = f"Entry {i + 1}"
        # Truncate long titles
        if len(first_line) > 60:
            first_line = first_line[:57] + "..."
        lines.append(f"- [{first_line}](entry://{child_id})")

    markdown = "\n".join(lines)

    cur.execute(
        """INSERT INTO entry (uuid, created_at, modified_at, markdown_text,
                              entry_type, is_all_day,
                              gregorian_year, gregorian_month, gregorian_day)
           VALUES (%s, make_date(%s, %s, %s)::timestamptz, now(), %s,
                   'daily_summary', true, %s, %s, %s)
           ON CONFLICT (gregorian_year, gregorian_month, gregorian_day)
               WHERE entry_type = 'daily_summary'
           DO NOTHING
           RETURNING id""",
        (entry_uuid, year, month, day, markdown, year, month, day),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    # Already exists
    cur.execute(
        """SELECT id FROM entry
           WHERE gregorian_year = %s AND gregorian_month = %s AND gregorian_day = %s
             AND entry_type = 'daily_summary'""",
        (year, month, day),
    )
    return cur.fetchone()[0]


def fix_trip_entries(cur):
    """Update trip_entry.entry_id to point to daily_summary where applicable."""
    cur.execute("""
        UPDATE trip_entry te
        SET entry_id = e.parent_entry_id
        FROM entry e
        WHERE te.entry_id = e.id
          AND e.parent_entry_id IS NOT NULL
          AND e.entry_type != 'daily_summary'
          AND EXISTS (
            SELECT 1 FROM entry ds
            WHERE ds.id = e.parent_entry_id AND ds.entry_type = 'daily_summary'
          )
    """)
    return cur.rowcount


def main() -> None:
    args = parse_args()

    dsn = settings.cross_dsn(settings.db_name, settings.db_user, settings.db_password)
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    end_date = date.fromisoformat(args.end_date) if args.end_date else None

    # Step 1: Find multi-entry days
    multi_days = find_multi_entry_days(cur, start_date, end_date)
    print(f"Found {len(multi_days)} multi-entry days")

    if args.dry_run:
        for year, month, day, entry_ids, previews in multi_days[:20]:
            print(f"  {day:02d}/{month:02d}/{year}: {len(entry_ids)} entries — IDs {list(entry_ids)}")
        if len(multi_days) > 20:
            print(f"  ... and {len(multi_days) - 20} more")
        return

    # Step 2: Create summaries and reparent
    created = 0
    consolidated = 0
    enriched = 0

    for i, (year, month, day, entry_ids, previews) in enumerate(multi_days):
        try:
            # Create summary
            summary_id = create_summary_entry(cur, year, month, day, list(entry_ids), list(previews))

            # Reparent all children
            cur.execute(
                """UPDATE entry SET parent_entry_id = %s
                   WHERE id = ANY(%s) AND entry_type != 'daily_summary'""",
                (summary_id, list(entry_ids)),
            )

            # Step 3: Consolidate structured data
            child_ids = list(entry_ids)
            stats = consolidate_structured_data(conn, summary_id, child_ids)
            if any(stats.values()):
                consolidated += 1

            # Step 4: Enrich from sources (optional)
            if not args.skip_enrichment:
                target = date(year, month, day)
                enrich_stats = enrich_from_sources(conn, settings, summary_id, target)
                if any(enrich_stats.values()):
                    enriched += 1

            created += 1

            # Batch commit
            if (i + 1) % args.batch_size == 0:
                conn.commit()
                print(f"  Progress: {i + 1}/{len(multi_days)} (committed)")

        except Exception as e:
            print(f"  ERROR on {day:02d}/{month:02d}/{year}: {e}", file=sys.stderr)
            conn.rollback()

    conn.commit()
    print(f"\nSummaries created: {created}")
    print(f"Days with consolidated data: {consolidated}")
    print(f"Days with new enrichment data: {enriched}")

    # Step 5: Fix trip_entry references
    if args.fix_trips:
        fixed = fix_trip_entries(cur)
        conn.commit()
        print(f"Trip entries re-pointed to summaries: {fixed}")

    conn.close()


if __name__ == "__main__":
    main()
