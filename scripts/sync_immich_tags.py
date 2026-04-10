#!/usr/bin/env python3
"""Reconcile Immich 'used:journal' tags with asset references in the journal DB.

Overnight two-way sync:
  - Assets referenced in DB but not tagged in Immich → add tag
  - Assets tagged in Immich but no longer referenced in DB → remove tag

Only tags are affected — assets themselves are never modified.

Usage:
    python scripts/sync_immich_tags.py
    python scripts/sync_immich_tags.py --dry-run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings

TAG_NAME = "used:journal"
BATCH_SIZE = 500


def ping_hc(suffix: str = ""):
    if not settings.hc_immich_tag_sync:
        return
    try:
        httpx.get(f"{settings.hc_base}/{settings.hc_immich_tag_sync}{suffix}", timeout=5)
    except Exception:
        pass


def get_db_asset_ids() -> set[str]:
    """Return all Immich asset IDs currently referenced in the journal DB."""
    dsn = settings.cross_dsn(settings.db_name, settings.db_user, settings.db_password)
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT immich_asset_id FROM (
                    SELECT immich_asset_id FROM attachment
                    WHERE immich_asset_id IS NOT NULL
                    UNION
                    SELECT cover_asset_id FROM trip
                    WHERE cover_asset_id IS NOT NULL
                    UNION
                    SELECT asset_id FROM trip_highlight
                    WHERE asset_id IS NOT NULL
                ) AS all_assets
            """)
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def ensure_tag(client: httpx.Client, headers: dict) -> str:
    """Get or create the tag, return its ID."""
    resp = client.post(
        f"{settings.immich_url}/api/tags",
        headers=headers,
        json={"name": TAG_NAME},
    )
    if resp.status_code in (200, 201):
        return resp.json()["id"]

    if resp.status_code in (400, 409):
        resp = client.get(f"{settings.immich_url}/api/tags", headers=headers)
        resp.raise_for_status()
        for tag in resp.json():
            if tag.get("name") == TAG_NAME:
                return tag["id"]

    raise RuntimeError(f"Failed to ensure tag '{TAG_NAME}': {resp.status_code} {resp.text}")


def get_tagged_asset_ids(client: httpx.Client, headers: dict, tag_id: str) -> set[str]:
    """Return all Immich asset IDs currently tagged with our tag."""
    asset_ids: set[str] = set()
    page = 1
    while True:
        resp = client.post(
            f"{settings.immich_url}/api/search/metadata",
            headers=headers,
            json={"takenAfter": "1970-01-01T00:00:00.000Z", "tagIds": [tag_id], "page": page, "size": 1000},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("assets", {}).get("items", [])
        if not items:
            break
        asset_ids.update(item["id"] for item in items)
        if len(items) < 1000:
            break
        page += 1
    return asset_ids


def sync_tags(client: httpx.Client, headers: dict, tag_id: str,
              to_add: set[str], to_remove: set[str], dry_run: bool) -> None:
    """Add and remove tag associations in batches."""
    if to_add:
        add_list = sorted(to_add)
        for i in range(0, len(add_list), BATCH_SIZE):
            batch = add_list[i:i + BATCH_SIZE]
            if dry_run:
                print(f"  [dry-run] Would tag {len(batch)} assets")
            else:
                resp = client.put(
                    f"{settings.immich_url}/api/tags/{tag_id}/assets",
                    headers=headers,
                    json={"ids": batch},
                )
                if resp.status_code not in (200, 201):
                    print(f"  WARNING: tag add batch failed: {resp.status_code} {resp.text}")

    if to_remove:
        remove_list = sorted(to_remove)
        for i in range(0, len(remove_list), BATCH_SIZE):
            batch = remove_list[i:i + BATCH_SIZE]
            if dry_run:
                print(f"  [dry-run] Would untag {len(batch)} assets")
            else:
                resp = client.request(
                    "DELETE",
                    f"{settings.immich_url}/api/tags/{tag_id}/assets",
                    headers=headers,
                    json={"ids": batch},
                )
                if resp.status_code not in (200, 204):
                    print(f"  WARNING: tag remove batch failed: {resp.status_code} {resp.text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Immich 'used:journal' tags")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without modifying Immich")
    args = parser.parse_args()

    if not args.dry_run:
        ping_hc("/start")

    rc = 0
    try:
        db_ids = get_db_asset_ids()
        print(f"Journal DB: {len(db_ids)} Immich assets referenced")

        api_key = settings.immich_tag_api_key or settings.immich_api_key
        headers = {"x-api-key": api_key}
        with httpx.Client(timeout=30) as client:
            tag_id = ensure_tag(client, headers)
            print(f"Tag '{TAG_NAME}': {tag_id}")

            tagged_ids = get_tagged_asset_ids(client, headers, tag_id)
            print(f"Immich tagged: {len(tagged_ids)} assets")

            to_add = db_ids - tagged_ids
            to_remove = tagged_ids - db_ids

            print(f"To add: {len(to_add)}, To remove: {len(to_remove)}")

            if to_add or to_remove:
                sync_tags(client, headers, tag_id, to_add, to_remove, args.dry_run)
                if not args.dry_run:
                    print("Sync complete")
            else:
                print("Already in sync")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        rc = 1

    if not args.dry_run:
        ping_hc(f"/{rc}" if rc else "")

    sys.exit(rc)


if __name__ == "__main__":
    main()
