from fastapi import APIRouter, Depends

from src.api.deps import get_conn, get_current_user
from src.api.models import TagOut

router = APIRouter()


@router.get("/tags", response_model=list[TagOut])
def list_tags(conn=Depends(get_conn), _user=Depends(get_current_user)):
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.name, COUNT(et.entry_id) as entry_count
        FROM tag t
        LEFT JOIN entry_tag et ON et.tag_id = t.id
        GROUP BY t.id
        ORDER BY entry_count DESC, t.name
    """)
    return [
        TagOut(id=r[0], name=r[1], entry_count=r[2])
        for r in cur.fetchall()
    ]
