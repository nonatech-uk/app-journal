from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from config.settings import settings
from src.api.deps import get_conn, get_current_user

router = APIRouter()

MIME_MAP = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "mov": "video/quicktime",
    "mp4": "video/mp4",
    "pdf": "application/pdf",
}


@router.get("/media/{attachment_id}")
def serve_media(
    attachment_id: int,
    thumb: bool = Query(False),
    conn=Depends(get_conn),
    _user=Depends(get_current_user),
):
    cur = conn.cursor()
    cur.execute(
        "SELECT local_path, type FROM attachment WHERE id = %s",
        (attachment_id,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        raise HTTPException(404, "Media not found")

    file_path = Path(settings.media_root) / row[0]
    if not file_path.exists():
        raise HTTPException(404, "File not found on disk")

    media_type = MIME_MAP.get(row[1], "application/octet-stream")
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
