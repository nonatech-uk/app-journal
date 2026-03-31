from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps

from config.settings import settings
from src.api.deps import get_conn, get_current_user
from src.services.immich import get_thumbnail

router = APIRouter()

MIME_MAP = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "mov": "video/quicktime",
    "mp4": "video/mp4",
    "pdf": "application/pdf",
    "audio": "audio/webm",
}

THUMB_SIZE = (800, 800)
THUMB_QUALITY = 75


def _get_or_create_thumb(attachment_id: int, original: Path) -> Path:
    thumb_dir = Path(settings.media_root) / "thumbs"
    thumb_dir.mkdir(exist_ok=True)
    thumb_path = thumb_dir / f"{attachment_id}.jpg"
    if not thumb_path.exists():
        with Image.open(original) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMB_SIZE)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(thumb_path, "JPEG", quality=THUMB_QUALITY)
    return thumb_path


@router.get("/media/{attachment_id}")
def serve_media(
    attachment_id: int,
    thumb: bool = Query(False),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    cur.execute(
        "SELECT local_path, type, immich_asset_id FROM attachment WHERE id = %s",
        (attachment_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Media not found")

    # If no local file but has Immich asset, proxy from Immich
    if not row[0] and row[2]:
        result = get_thumbnail(settings, row[2])
        if not result:
            raise HTTPException(404, "Immich thumbnail not available")
        data, content_type = result
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    if not row[0]:
        raise HTTPException(404, "Media not found")

    file_path = Path(settings.media_root) / row[0]
    if not file_path.exists():
        raise HTTPException(404, "File not found on disk")

    media_type = MIME_MAP.get(row[1], "application/octet-stream")

    if thumb and row[1] in ("jpeg", "png"):
        thumb_path = _get_or_create_thumb(attachment_id, file_path)
        return FileResponse(
            thumb_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
