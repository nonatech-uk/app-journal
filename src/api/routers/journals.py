from fastapi import APIRouter, Depends

from src.api.deps import get_conn, get_current_user
from src.api.models import JournalOut

router = APIRouter()


@router.get("/journals", response_model=list[JournalOut])
def list_journals(conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT j.id, j.name, j.color_hex, j.description,
               COUNT(e.id) as entry_count
        FROM journal j
        LEFT JOIN entry e ON e.journal_id = j.id
        WHERE j.is_trash = false
        GROUP BY j.id
        ORDER BY j.name
    """)
    return [
        JournalOut(
            id=r[0], name=r[1], color_hex=r[2],
            description=r[3], entry_count=r[4],
        )
        for r in cur.fetchall()
    ]
