"""Daily summary enrichment API — trigger consolidation and source top-up."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from config.settings import settings
from src.api.deps import get_conn, require_admin
from src.services.daily_summary import run_daily_enrichment

router = APIRouter()


@router.post("/daily-summary/run")
def run_enrichment(
    target_date: date | None = Query(None, alias="date"),
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Run daily enrichment for a single date (default: yesterday)."""
    return run_daily_enrichment(conn, settings, target_date)


@router.post("/daily-summary/backfill")
def backfill_enrichment(
    start: date = Query(...),
    end: date = Query(...),
    conn=Depends(get_conn),
    _user=Depends(require_admin),
):
    """Run daily enrichment for a date range."""
    results = []
    current = start
    while current <= end:
        result = run_daily_enrichment(conn, settings, current)
        results.append(result)
        current += timedelta(days=1)
    return {
        "processed": len(results),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "results": results,
    }
