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
    window_start = entry_date - timedelta(hours=2)
    window_end = entry_date + timedelta(hours=2)

    result = {
        "scrobbles": [],
        "transactions": [],
        "gps_summary": None,
        "tautulli_watches": [],
    }

    # Scrobbles (±2 hours around entry time)
    scrobble_dsn = settings.cross_dsn(settings.scrobble_db_name, settings.scrobble_db_user, settings.scrobble_db_password)
    if settings.scrobble_db_password:
        result["scrobbles"] = _safe_query(
            scrobble_dsn,
            """SELECT artist, track, album, scrobbled_at
               FROM scrobble
               WHERE scrobbled_at BETWEEN %s AND %s
               ORDER BY scrobbled_at""",
            (window_start, window_end),
        )

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

    # GPS summary (same day)
    mylocation_dsn = settings.cross_dsn(settings.mylocation_db_name, settings.mylocation_db_user, settings.mylocation_db_password)
    if settings.mylocation_db_password:
        gps_rows = _safe_query(
            mylocation_dsn,
            """SELECT city, country, date, source
               FROM daily_location
               WHERE date = %s::date""",
            (entry_date,),
        )
        if gps_rows:
            result["gps_summary"] = gps_rows[0]

    return result
