"""Proxy GPS track SVGs from the my-locations service."""

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from config.settings import settings
from src.api.deps import get_current_user

router = APIRouter()

_FORWARD_HEADERS = ("Remote-Email", "Remote-Name", "Remote-User")


def _proxy_svg(request: Request, path: str, params: dict) -> Response:
    """Fetch an SVG from the my-locations API, forwarding auth headers."""
    url = f"{settings.mylocation_api_url.rstrip('/')}/api/v1/gps/{path}"
    headers = {
        h: request.headers[h]
        for h in _FORWARD_HEADERS
        if h in request.headers
    }
    resp = httpx.get(url, params=params, headers=headers, timeout=10)
    if resp.status_code == 204:
        return Response(status_code=204)
    if resp.status_code != 200:
        return Response(status_code=resp.status_code)
    return Response(
        content=resp.content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/gps/track-svg")
def track_svg(
    request: Request,
    date: str = Query(...),
    width: int = Query(200, ge=50, le=800),
    height: int = Query(150, ge=50, le=600),
    _user=Depends(get_current_user),
):
    return _proxy_svg(request, "track-svg", {"date": date, "width": width, "height": height})


@router.get("/gps/activity-track-svg")
def activity_track_svg(
    request: Request,
    strava_id: int = Query(...),
    width: int = Query(200, ge=50, le=800),
    height: int = Query(150, ge=50, le=600),
    _user=Depends(get_current_user),
):
    return _proxy_svg(request, "activity-track-svg", {"strava_id": strava_id, "width": width, "height": height})
