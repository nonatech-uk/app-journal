#!/usr/bin/env python3
"""Flight enrichment — enrich pipeline-ingested flights with FlightAware and OpenFlights data.

Usage:
    python scripts/flight_enrich.py
    python scripts/flight_enrich.py --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings
from src.services.flights.enrich import run_enrichment

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


def main():
    parser = argparse.ArgumentParser(description="Enrich pipeline flights")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be enriched without changing data")
    args = parser.parse_args()

    api_key = settings.flightaware_api_key
    if not api_key:
        logging.warning("FLIGHTAWARE_API_KEY not set — only OpenFlights enrichment available")

    ping_hc("/start")

    conn = psycopg2.connect(settings.dsn)
    try:
        result = run_enrichment(conn, api_key, dry_run=args.dry_run)
    finally:
        conn.close()

    total = result["total"]
    report_lines = [
        f"Processed {total} flight(s): {result['enriched']} enriched, "
        f"{result['no_fa_data']} no FA data, {result['errors']} errors"
    ]
    report_lines.extend(result["summaries"])
    report = "\n".join(report_lines)
    print(report)

    if result["errors"] > 0 or result["no_fa_data"] > 0:
        ping_hc("/fail", report)
        return 1
    else:
        if total > 0:
            ping_hc("", report)
        else:
            ping_hc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
