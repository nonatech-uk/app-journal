"""Immich service — photo search, thumbnails, and asset download."""

import os
from pathlib import Path

import httpx


def _headers(settings) -> dict:
    return {"x-api-key": settings.immich_api_key, "Accept": "application/json"}


def search_smart(settings, query: str, limit: int = 20) -> list[dict]:
    """CLIP-based smart search in Immich."""
    if not settings.immich_api_key:
        return []
    try:
        resp = httpx.post(
            f"{settings.immich_url}/api/search/smart",
            json={"query": query, "page": 1, "size": limit},
            headers=_headers(settings),
            timeout=15,
        )
        resp.raise_for_status()
        assets = resp.json().get("assets", {}).get("items", [])
        return [_summarise_asset(a) for a in assets]
    except Exception:
        return []


def search_recent(settings, days: int = 7, limit: int = 20) -> list[dict]:
    """Get recent photos from Immich by date."""
    if not settings.immich_api_key:
        return []
    try:
        from datetime import datetime, timedelta, timezone
        after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        resp = httpx.post(
            f"{settings.immich_url}/api/search/metadata",
            json={"takenAfter": after, "order": "desc", "size": limit},
            headers=_headers(settings),
            timeout=15,
        )
        resp.raise_for_status()
        assets = resp.json().get("assets", {}).get("items", [])
        return [_summarise_asset(a) for a in assets]
    except Exception:
        return []


def get_thumbnail(settings, asset_id: str) -> tuple[bytes, str] | None:
    """Fetch thumbnail bytes for an asset. Returns (bytes, content_type) or None."""
    if not settings.immich_api_key:
        return None
    try:
        resp = httpx.get(
            f"{settings.immich_url}/api/assets/{asset_id}/thumbnail",
            headers={"x-api-key": settings.immich_api_key},
            timeout=10,
        )
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "image/jpeg")
        return resp.content, ct
    except Exception:
        return None


def download_asset(settings, asset_id: str, media_root: str, entry_uuid: str) -> dict | None:
    """Download an original asset from Immich and save to media storage.

    Returns attachment metadata dict or None on failure.
    """
    if not settings.immich_api_key:
        return None
    try:
        # Get asset info first
        info_resp = httpx.get(
            f"{settings.immich_url}/api/assets/{asset_id}",
            headers=_headers(settings),
            timeout=10,
        )
        info_resp.raise_for_status()
        info = info_resp.json()

        # Download original
        dl_resp = httpx.get(
            f"{settings.immich_url}/api/assets/{asset_id}/original",
            headers={"x-api-key": settings.immich_api_key},
            timeout=60,
        )
        dl_resp.raise_for_status()

        # Determine filename and type
        original_name = info.get("originalFileName", f"{asset_id}.jpg")
        ext = Path(original_name).suffix.lower().lstrip(".")
        if ext in ("jpg",):
            ext = "jpeg"
        media_type = ext  # jpeg, png, mov, mp4, etc.

        # Save to disk
        entry_dir = Path(media_root) / entry_uuid
        entry_dir.mkdir(parents=True, exist_ok=True)
        dest = entry_dir / original_name
        dest.write_bytes(dl_resp.content)
        relative_path = f"{entry_uuid}/{original_name}"

        # Extract EXIF metadata from info
        exif = info.get("exifInfo", {})
        return {
            "type": media_type,
            "filename": original_name,
            "file_size": len(dl_resp.content),
            "width": exif.get("exifImageWidth"),
            "height": exif.get("exifImageHeight"),
            "camera_make": exif.get("make"),
            "camera_model": exif.get("model"),
            "lens_model": exif.get("lensModel"),
            "iso": exif.get("iso"),
            "f_number": exif.get("fNumber"),
            "focal_length": exif.get("focalLength"),
            "date": info.get("fileCreatedAt"),
            "local_path": relative_path,
            "immich_asset_id": asset_id,
        }
    except Exception:
        return None


def _summarise_asset(asset: dict) -> dict:
    """Extract key fields from an Immich asset response."""
    return {
        "id": asset.get("id"),
        "type": asset.get("type", "IMAGE"),
        "original_filename": asset.get("originalFileName"),
        "created_at": asset.get("fileCreatedAt"),
        "thumbnail_url": f"/api/v1/immich/asset/{asset['id']}/thumbnail",
    }
