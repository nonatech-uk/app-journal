"""Location services — current GPS position and reverse geocoding."""

import httpx
import psycopg2


def get_current_location(settings) -> dict | None:
    """Get the most recent GPS point from the mylocation database."""
    dsn = settings.cross_dsn(
        settings.mylocation_db_name,
        settings.mylocation_db_user,
        settings.mylocation_db_password,
    )
    if not settings.mylocation_db_password:
        return None
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            "SELECT lat, lon, ts FROM gps_points ORDER BY ts DESC LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        return {"latitude": float(row[0]), "longitude": float(row[1]), "timestamp": row[2].isoformat()}
    except Exception:
        return None


def reverse_geocode(lat: float, lon: float) -> dict:
    """Reverse geocode coordinates via Nominatim (OpenStreetMap)."""
    result = {"place_name": None, "locality": None, "admin_area": None, "country": None}
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 16},
            headers={"User-Agent": "journal-app/1.0 (personal use)"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        addr = data.get("address", {})
        result["place_name"] = data.get("display_name", "").split(",")[0].strip() or None
        result["locality"] = addr.get("city") or addr.get("town") or addr.get("village") or None
        result["admin_area"] = addr.get("state") or addr.get("county") or None
        result["country"] = addr.get("country") or None
    except Exception:
        pass
    return result
