"""Immich proxy endpoints — search and thumbnail proxying."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from config.settings import settings
from src.api.deps import get_current_user
from src.services.immich import get_thumbnail, search_recent, search_smart

router = APIRouter()


@router.get("/immich/search")
def immich_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    _user=Depends(get_current_user),
):
    """CLIP-based smart search in Immich."""
    return search_smart(settings, q, limit)


@router.get("/immich/search/recent")
def immich_search_recent(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=50),
    _user=Depends(get_current_user),
):
    """Get recent photos from Immich."""
    return search_recent(settings, days, limit)


@router.get("/immich/asset/{asset_id}/thumbnail")
def immich_thumbnail(asset_id: str, _user=Depends(get_current_user)):
    """Proxy an Immich asset thumbnail."""
    result = get_thumbnail(settings, asset_id)
    if not result:
        raise HTTPException(404, "Thumbnail not found")
    data, content_type = result
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )
