"""Tautulli service — recent media watches from Plex."""

import httpx


def get_recent_watches(settings, limit: int = 5) -> list[dict]:
    """Get recent watch history from Tautulli."""
    if not settings.tautulli_api_key:
        return []
    try:
        resp = httpx.get(
            f"{settings.tautulli_url}/api/v2",
            params={
                "apikey": settings.tautulli_api_key,
                "cmd": "get_history",
                "length": limit,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        records = data.get("response", {}).get("data", {}).get("data", [])
        return [
            {
                "title": r.get("full_title") or r.get("title"),
                "media_type": r.get("media_type"),
                "year": r.get("year"),
                "watched_at": r.get("date"),
            }
            for r in records
        ]
    except Exception:
        return []
