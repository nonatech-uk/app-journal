#!/usr/bin/env python3
"""Flight enrichment — enrich pipeline-ingested flights with FlightAware and OpenFlights data,
then generate aircraft narratives for any registrations missing them.

Usage:
    python scripts/flight_enrich.py
    python scripts/flight_enrich.py --dry-run
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings
from src.services.flights.enrich import run_backfill, run_enrichment
from src.services.flights.narrative import generate_aircraft_narrative

HC_UUID = "30953ebe-ff22-49d0-afae-3829e0465229"
HC_BASE = "https://hc.mees.st/ping"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def ping_hc(suffix: str = "", body: str = ""):
    try:
        url = f"{HC_BASE}/{HC_UUID}{suffix}"
        if body:
            httpx.post(url, content=body, timeout=5)
        else:
            httpx.get(url, timeout=5)
    except Exception:
        pass


def generate_missing_narratives(conn, dry_run: bool = False) -> dict:
    """Find registrations without cached narratives and generate them."""
    cur = conn.cursor()

    # Find registrations without narratives
    cur.execute("""
        SELECT DISTINCT t.registration,
               COALESCE(
                   (SELECT aircraft_type FROM flight
                    WHERE flight.registration = t.registration
                      AND aircraft_type IS NOT NULL LIMIT 1),
                   (SELECT aircraft_type FROM ga_flight
                    WHERE ga_flight.registration = t.registration
                      AND aircraft_type IS NOT NULL LIMIT 1)
               ) AS aircraft_type
        FROM (
            SELECT registration FROM flight
            WHERE registration IS NOT NULL AND is_route = FALSE
            UNION
            SELECT registration FROM ga_flight
            WHERE registration IS NOT NULL
        ) t
        WHERE NOT EXISTS (
            SELECT 1 FROM aircraft_narrative
            WHERE aircraft_narrative.registration = t.registration
        )
        ORDER BY t.registration
    """)
    missing = cur.fetchall()

    # Find stale narratives (older than 365 days)
    cur.execute("""
        SELECT an.registration,
               COALESCE(
                   (SELECT aircraft_type FROM flight
                    WHERE flight.registration = an.registration
                      AND aircraft_type IS NOT NULL LIMIT 1),
                   (SELECT aircraft_type FROM ga_flight
                    WHERE ga_flight.registration = an.registration
                      AND aircraft_type IS NOT NULL LIMIT 1)
               ) AS aircraft_type
        FROM aircraft_narrative an
        WHERE an.generated_at < now() - interval '365 days'
        ORDER BY an.registration
    """)
    stale = cur.fetchall()

    generated = 0
    refreshed = 0
    failed = 0

    if missing:
        logging.info("Generating narratives for %d new registration(s)", len(missing))

    for reg, aircraft_type in missing:
        if dry_run:
            logging.info("  [DRY RUN] Would generate narrative for %s (%s)", reg, aircraft_type or "unknown type")
            continue

        text, cache = generate_aircraft_narrative(
            reg, aircraft_type, settings.anthropic_api_key,
            register_path=settings.iaa_register_path,
            airframes_user=settings.airframes_org_user,
            airframes_password=settings.airframes_org_password,
        )
        if text:
            cur.execute(
                """INSERT INTO aircraft_narrative (registration, narrative, model, register_data)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (registration) DO NOTHING""",
                (reg, text, "claude-sonnet-4-6", json.dumps(cache) if cache else None),
            )
            conn.commit()
            generated += 1
            logging.info("  %s: generated (%d chars)", reg, len(text))
        else:
            failed += 1
            logging.warning("  %s: generation failed", reg)

        time.sleep(20)

    if stale:
        logging.info("Refreshing %d stale narrative(s)", len(stale))

    for reg, aircraft_type in stale:
        if dry_run:
            logging.info("  [DRY RUN] Would refresh narrative for %s", reg)
            continue

        text, cache = generate_aircraft_narrative(
            reg, aircraft_type, settings.anthropic_api_key,
            register_path=settings.iaa_register_path,
            airframes_user=settings.airframes_org_user,
            airframes_password=settings.airframes_org_password,
        )
        if text:
            # Archive old version
            cur.execute(
                """INSERT INTO aircraft_narrative_history
                   (registration, narrative, model, register_data, generated_at)
                   SELECT registration, narrative, model, register_data, generated_at
                   FROM aircraft_narrative WHERE registration = %s""",
                (reg,),
            )
            cur.execute(
                """UPDATE aircraft_narrative
                   SET narrative = %s, model = %s, register_data = %s, generated_at = now()
                   WHERE registration = %s""",
                (text, "claude-sonnet-4-6", json.dumps(cache) if cache else None, reg),
            )
            conn.commit()
            refreshed += 1
            logging.info("  %s: refreshed", reg)
        else:
            failed += 1
            logging.warning("  %s: refresh failed", reg)

        time.sleep(20)

    return {
        "missing": len(missing),
        "stale": len(stale),
        "generated": generated,
        "refreshed": refreshed,
        "failed": failed,
    }


def main():
    parser = argparse.ArgumentParser(description="Enrich pipeline flights + generate aircraft narratives")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be enriched without changing data")
    parser.add_argument("--backfill", action="store_true", help="Backfill all flights with gaps (any source/date)")
    args = parser.parse_args()

    api_key = settings.flightaware_api_key
    if not api_key:
        logging.warning("FLIGHTAWARE_API_KEY not set — only OpenFlights enrichment available")

    ping_hc("/start")

    # Phase 1: Flight enrichment
    conn = psycopg2.connect(settings.dsn)
    try:
        if args.backfill:
            result = run_backfill(conn, api_key, dry_run=args.dry_run)
        else:
            result = run_enrichment(conn, api_key, dry_run=args.dry_run)
    finally:
        conn.close()

    total = result["total"]
    report_lines = [
        f"Phase 1 — Flights: {total} processed, {result['enriched']} enriched, "
        f"{result['no_fa_data']} no FA data, {result['errors']} errors"
    ]
    report_lines.extend(result["summaries"])
    had_error = result["errors"] > 0

    # Phase 2: Aircraft narratives
    conn = psycopg2.connect(settings.dsn)
    try:
        narr = generate_missing_narratives(conn, dry_run=args.dry_run)
    finally:
        conn.close()

    narr_total = narr["missing"] + narr["stale"]
    if narr_total > 0 or args.dry_run:
        report_lines.append(
            f"Phase 2 — Narratives: {narr['generated']} generated, "
            f"{narr['refreshed']} refreshed, {narr['failed']} failed "
            f"(from {narr['missing']} missing + {narr['stale']} stale)"
        )
    if narr["failed"] > 0:
        had_error = True

    report = "\n".join(report_lines)
    print(report)

    if had_error:
        ping_hc("/fail", report)
        return 1
    else:
        if total > 0 or narr_total > 0:
            ping_hc("", report)
        else:
            ping_hc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
