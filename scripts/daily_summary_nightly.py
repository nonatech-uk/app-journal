#!/usr/bin/env python3
"""Daily summary enrichment — nightly job to consolidate and top up structured data.

Usage:
    python scripts/daily_summary_nightly.py [--date YYYY-MM-DD]
    python scripts/daily_summary_nightly.py --start-date 2024-01-01 --end-date 2024-12-31
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings
from src.services.daily_summary import run_daily_enrichment

def ping_hc(suffix: str = ""):
    if not settings.hc_daily_enrichment:
        return
    try:
        httpx.get(f"{settings.hc_base}/{settings.hc_daily_enrichment}{suffix}", timeout=5)
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily summary enrichment job")
    parser.add_argument("--date", type=str, default=None, help="Target date (YYYY-MM-DD, default: yesterday)")
    parser.add_argument("--start-date", type=str, default=None, help="Start of date range (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="End of date range (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be processed without writing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    is_nightly = not args.start_date and not args.end_date and not args.dry_run

    if is_nightly:
        ping_hc("/start")

    dsn = settings.cross_dsn(settings.db_name, settings.db_user, settings.db_password)
    conn = psycopg2.connect(dsn)
    had_error = False

    if args.start_date and args.end_date:
        # Range mode
        current = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
        total = (end - current).days + 1
        processed = 0
        enriched = 0

        print(f"Processing {total} days: {current} to {end}")

        while current <= end:
            if args.dry_run:
                print(f"  [DRY RUN] Would process {current}")
            else:
                try:
                    result = run_daily_enrichment(conn, settings, current)
                    if "skipped" not in result:
                        enriched += 1
                        if any(result.get("enrichment", {}).values()):
                            e = result["enrichment"]
                            print(f"  {current}: enriched — {e}")
                except Exception as e:
                    print(f"  {current}: ERROR — {e}", file=sys.stderr)
                    conn.rollback()
                    had_error = True

            processed += 1
            if processed % 50 == 0:
                print(f"  Progress: {processed}/{total}")
            current += timedelta(days=1)

        print(f"\nDone. Processed: {processed}, enriched: {enriched}")
    else:
        # Single date mode
        target = date.fromisoformat(args.date) if args.date else None
        if args.dry_run:
            target = target or (date.today() - timedelta(days=1))
            print(f"[DRY RUN] Would process {target}")
            conn.close()
            return

        try:
            result = run_daily_enrichment(conn, settings, target)
            print(f"Result: {result}")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            had_error = True

    conn.close()

    if is_nightly:
        ping_hc("/fail" if had_error else "")

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
