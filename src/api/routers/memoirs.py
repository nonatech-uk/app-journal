"""Memoirs — narrative sections covering periods of life, with hierarchy."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.settings import settings
from src.api.deps import get_conn, get_current_user, require_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MemoirCreate(BaseModel):
    title: str
    parent_id: int | None = None
    start_year: int | None = None
    start_month: int | None = None
    end_year: int | None = None
    end_month: int | None = None
    date_label: str | None = None
    description: str | None = None
    markdown_text: str | None = None
    cover_asset_id: str | None = None
    sort_order: int = 0


class MemoirUpdate(BaseModel):
    title: str | None = None
    start_year: int | None = -1  # sentinel
    start_month: int | None = -1
    end_year: int | None = -1
    end_month: int | None = -1
    date_label: str | None = "__UNSET__"
    description: str | None = "__UNSET__"
    markdown_text: str | None = "__UNSET__"
    cover_asset_id: str | None = "__UNSET__"
    sort_order: int | None = None


class ReorderItem(BaseModel):
    id: int
    sort_order: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _memoir_summary(row, child_count: int = 0, attachment_count: int = 0) -> dict:
    return {
        "id": row[0],
        "parent_id": row[1],
        "title": row[2],
        "start_year": row[3],
        "start_month": row[4],
        "end_year": row[5],
        "end_month": row[6],
        "date_label": row[7],
        "description": row[8],
        "entry_id": row[9],
        "cover_asset_id": row[10],
        "sort_order": row[11],
        "created_at": row[12],
        "modified_at": row[13],
        "child_count": child_count,
        "attachment_count": attachment_count,
    }


def _memoir_detail(cur, memoir_id: int) -> dict:
    """Build full memoir detail including backing entry content and children."""
    cur.execute("""
        SELECT m.id, m.parent_id, m.title, m.start_year, m.start_month,
               m.end_year, m.end_month, m.date_label, m.description,
               m.entry_id, m.cover_asset_id, m.sort_order,
               m.created_at, m.modified_at
        FROM memoir m WHERE m.id = %s
    """, (memoir_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Memoir not found")

    entry_id = row[9]
    result = _memoir_summary(row)

    # Backing entry content
    result["markdown_text"] = None
    result["attachments"] = []
    if entry_id:
        cur.execute("SELECT markdown_text FROM entry WHERE id = %s", (entry_id,))
        e_row = cur.fetchone()
        if e_row:
            result["markdown_text"] = e_row[0]

        # Attachments
        cur.execute("""
            SELECT id, uuid, type, filename, file_size, width, height,
                   order_in_entry, caption, duration, is_favorite,
                   transcription, date, local_path, immich_asset_id
            FROM attachment WHERE entry_id = %s
            ORDER BY order_in_entry, id
        """, (entry_id,))
        for a in cur.fetchall():
            att = {
                "id": a[0], "uuid": a[1], "type": a[2], "filename": a[3],
                "file_size": a[4], "width": a[5], "height": a[6],
                "order_in_entry": a[7], "caption": a[8], "duration": a[9],
                "is_favorite": a[10], "transcription": a[11], "date": a[12],
                "local_path": a[13], "immich_asset_id": a[14],
                "media_url": f"/api/v1/media/{a[0]}",
                "thumbnail_url": f"/api/v1/media/{a[0]}?thumb=1",
            }
            result["attachments"].append(att)

    # Children (sub-pages)
    cur.execute("""
        SELECT m.id, m.parent_id, m.title, m.start_year, m.start_month,
               m.end_year, m.end_month, m.date_label, m.description,
               m.entry_id, m.cover_asset_id, m.sort_order,
               m.created_at, m.modified_at
        FROM memoir m WHERE m.parent_id = %s
        ORDER BY m.sort_order, m.start_year NULLS LAST, m.title
    """, (memoir_id,))
    children = []
    for child_row in cur.fetchall():
        # Count attachments for each child
        child_entry_id = child_row[9]
        att_count = 0
        if child_entry_id:
            cur.execute("SELECT COUNT(*) FROM attachment WHERE entry_id = %s", (child_entry_id,))
            att_count = cur.fetchone()[0]
        children.append(_memoir_summary(child_row, attachment_count=att_count))
    result["children"] = children
    result["child_count"] = len(children)

    # Linked journal entries
    cur.execute("""
        SELECT e.id, e.uuid, e.created_at, LEFT(e.markdown_text, 200) AS preview,
               l.place_name
        FROM memoir_entry me
        JOIN entry e ON e.id = me.entry_id
        LEFT JOIN location l ON l.entry_id = e.id AND l.location_type = 'primary'
        WHERE me.memoir_id = %s
        ORDER BY e.created_at
    """, (memoir_id,))
    linked = []
    for le in cur.fetchall():
        linked.append({
            "id": le[0], "uuid": le[1], "created_at": le[2],
            "preview": le[3], "place_name": le[4],
        })
    result["linked_entries"] = linked

    # Parent breadcrumb
    if row[1]:  # parent_id
        cur.execute("SELECT id, title FROM memoir WHERE id = %s", (row[1],))
        p = cur.fetchone()
        result["parent"] = {"id": p[0], "title": p[1]} if p else None
    else:
        result["parent"] = None

    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/memoirs")
def list_memoirs(conn=Depends(get_conn), _user=Depends(get_current_user)):
    """List top-level memoirs with child counts."""
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.parent_id, m.title, m.start_year, m.start_month,
               m.end_year, m.end_month, m.date_label, m.description,
               m.entry_id, m.cover_asset_id, m.sort_order,
               m.created_at, m.modified_at,
               (SELECT COUNT(*) FROM memoir c WHERE c.parent_id = m.id) AS child_count,
               COALESCE((SELECT COUNT(*) FROM attachment a WHERE a.entry_id = m.entry_id), 0) AS att_count
        FROM memoir m
        WHERE m.parent_id IS NULL
        ORDER BY m.sort_order, m.start_year DESC NULLS LAST, m.title
    """)
    items = []
    for row in cur.fetchall():
        s = _memoir_summary(row, child_count=row[14], attachment_count=row[15])
        items.append(s)
    return {"items": items, "total": len(items)}


@router.get("/memoirs/{memoir_id}")
def get_memoir(memoir_id: int, conn=Depends(get_conn), _user=Depends(get_current_user)):
    """Get memoir detail with content, attachments, children, and linked entries."""
    cur = conn.cursor()
    return _memoir_detail(cur, memoir_id)


@router.post("/memoirs")
def create_memoir(body: MemoirCreate, conn=Depends(get_conn), _user=Depends(require_admin)):
    """Create a memoir with a backing entry for content."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc)
    entry_uuid = str(uuid.uuid4()).upper()

    # Create backing entry
    cur.execute(
        """INSERT INTO entry (uuid, created_at, modified_at, markdown_text,
                              entry_type, gregorian_year, gregorian_month, gregorian_day)
           VALUES (%s, %s, %s, %s, 'memoir', %s, %s, %s)
           RETURNING id""",
        (entry_uuid, now, now, body.markdown_text or "",
         now.year, now.month, now.day),
    )
    entry_id = cur.fetchone()[0]

    # Create memoir
    cur.execute(
        """INSERT INTO memoir (parent_id, title, start_year, start_month,
                               end_year, end_month, date_label, description,
                               entry_id, cover_asset_id, sort_order)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (body.parent_id, body.title, body.start_year, body.start_month,
         body.end_year, body.end_month, body.date_label, body.description,
         entry_id, body.cover_asset_id, body.sort_order),
    )
    memoir_id = cur.fetchone()[0]
    conn.commit()

    return _memoir_detail(cur, memoir_id)


@router.put("/memoirs/{memoir_id}")
def update_memoir(memoir_id: int, body: MemoirUpdate, conn=Depends(get_conn), _user=Depends(require_admin)):
    """Update memoir metadata and/or backing entry content."""
    cur = conn.cursor()

    # Get current memoir
    cur.execute("SELECT entry_id FROM memoir WHERE id = %s", (memoir_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Memoir not found")
    entry_id = row[0]

    # Update memoir fields
    updates = []
    params = []
    if body.title is not None:
        updates.append("title = %s")
        params.append(body.title)
    if body.start_year != -1:
        updates.append("start_year = %s")
        params.append(body.start_year)
    if body.start_month != -1:
        updates.append("start_month = %s")
        params.append(body.start_month)
    if body.end_year != -1:
        updates.append("end_year = %s")
        params.append(body.end_year)
    if body.end_month != -1:
        updates.append("end_month = %s")
        params.append(body.end_month)
    if body.date_label != "__UNSET__":
        updates.append("date_label = %s")
        params.append(body.date_label)
    if body.description != "__UNSET__":
        updates.append("description = %s")
        params.append(body.description)
    if body.cover_asset_id != "__UNSET__":
        updates.append("cover_asset_id = %s")
        params.append(body.cover_asset_id)
    if body.sort_order is not None:
        updates.append("sort_order = %s")
        params.append(body.sort_order)

    if updates:
        updates.append("modified_at = now()")
        params.append(memoir_id)
        cur.execute(f"UPDATE memoir SET {', '.join(updates)} WHERE id = %s", params)

    # Update backing entry markdown
    if body.markdown_text != "__UNSET__" and entry_id:
        cur.execute(
            "UPDATE entry SET markdown_text = %s, modified_at = now() WHERE id = %s",
            (body.markdown_text, entry_id),
        )

    conn.commit()
    return _memoir_detail(cur, memoir_id)


@router.delete("/memoirs/{memoir_id}")
def delete_memoir(memoir_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    """Delete memoir, its children, and their backing entries."""
    cur = conn.cursor()

    # Collect all entry_ids to delete (this memoir + children)
    cur.execute("""
        SELECT entry_id FROM memoir WHERE id = %s OR parent_id = %s
    """, (memoir_id, memoir_id))
    entry_ids = [r[0] for r in cur.fetchall() if r[0]]

    # Delete memoir (CASCADE deletes children and memoir_entry rows)
    cur.execute("DELETE FROM memoir WHERE id = %s", (memoir_id,))

    # Delete backing entries
    if entry_ids:
        cur.execute(
            "DELETE FROM entry WHERE id = ANY(%s) AND entry_type = 'memoir'",
            (entry_ids,),
        )

    conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Entry linking
# ---------------------------------------------------------------------------

@router.post("/memoirs/{memoir_id}/entries")
def link_entry(memoir_id: int, entry_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    """Link a journal entry to this memoir."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memoir_entry (memoir_id, entry_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (memoir_id, entry_id),
    )
    conn.commit()
    return {"ok": True}


@router.delete("/memoirs/{memoir_id}/entries/{entry_id}")
def unlink_entry(memoir_id: int, entry_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    """Unlink a journal entry from this memoir."""
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM memoir_entry WHERE memoir_id = %s AND entry_id = %s",
        (memoir_id, entry_id),
    )
    conn.commit()
    return {"ok": True}


@router.post("/memoirs/{memoir_id}/entries/auto")
def auto_link_entries(memoir_id: int, conn=Depends(get_conn), _user=Depends(require_admin)):
    """Auto-link journal entries whose dates fall within this memoir's year range."""
    cur = conn.cursor()
    cur.execute("SELECT start_year, end_year FROM memoir WHERE id = %s", (memoir_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Memoir not found")
    start_year, end_year = row
    if not start_year:
        return {"linked": 0}

    end = end_year or start_year

    cur.execute("""
        INSERT INTO memoir_entry (memoir_id, entry_id)
        SELECT %s, e.id FROM entry e
        WHERE e.gregorian_year BETWEEN %s AND %s
          AND e.entry_type = 'diary'
          AND NOT EXISTS (
              SELECT 1 FROM memoir_entry me
              WHERE me.memoir_id = %s AND me.entry_id = e.id
          )
    """, (memoir_id, start_year, end, memoir_id))
    linked = cur.rowcount
    conn.commit()
    return {"linked": linked}


@router.put("/memoirs/{memoir_id}/reorder")
def reorder_children(memoir_id: int, items: list[ReorderItem], conn=Depends(get_conn), _user=Depends(require_admin)):
    """Update sort_order for children of a memoir."""
    cur = conn.cursor()
    for item in items:
        cur.execute(
            "UPDATE memoir SET sort_order = %s WHERE id = %s AND parent_id = %s",
            (item.sort_order, item.id, memoir_id),
        )
    conn.commit()
    return {"ok": True}
