#!/usr/bin/env python3
"""Extract URLs from journal entries and save to Linkwarden.

Nightly sync:
  - Scan all journal entry markdown for http/https URLs
  - Create any missing links in Linkwarden's "Journal" collection
  - Add backlinks to journal entries in each link's description
  - URLs already in the Journal collection are skipped (idempotent)
  - URLs in other Linkwarden collections are NOT skipped (intentional duplicates)

Usage:
    python scripts/sync_linkwarden_urls.py
    python scripts/sync_linkwarden_urls.py --dry-run
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings

COLLECTION_NAME = "Journal"
JOURNAL_BASE_URL = "https://journal.mees.st"
HC_UUID = "04df5f9c-25dc-44fb-9205-f6927a970cdb"

URL_PATTERN = re.compile(r'https?://[^\s\)\]>"\']+')
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)')
BACKLINK_PATTERN = re.compile(r'journal\.mees\.st/entry/\d+')

EXCLUDE_DOMAINS = {"hc.mees.st", "localhost", "127.0.0.1", "pix.mees.st"}


def ping_hc(suffix: str = ""):
    if not HC_UUID:
        return
    try:
        httpx.get(f"{settings.hc_base}/{HC_UUID}{suffix}", timeout=5)
    except Exception:
        pass


def clean_url(url: str) -> str:
    """Strip backslash escaping and trailing punctuation."""
    url = url.replace("\\", "")
    while url and url[-1] in (".", ",", ";", ":", "!"):
        url = url[:-1]
    return url


def is_excluded(url: str) -> bool:
    """Check if URL belongs to an excluded domain."""
    try:
        host = urlparse(url).hostname or ""
        return host in EXCLUDE_DOMAINS
    except Exception:
        return True


def extract_urls(markdown: str) -> list[dict]:
    """Extract URLs from markdown text, returning [{url, name}]."""
    found: dict[str, str | None] = {}

    # First pass: markdown links [name](url) — captures the link text
    for name, url in MARKDOWN_LINK_PATTERN.findall(markdown):
        url = clean_url(url)
        if url and not is_excluded(url) and url not in found:
            found[url] = name

    # Second pass: bare URLs (dedup against already-found markdown links)
    for url in URL_PATTERN.findall(markdown):
        url = clean_url(url)
        if url and not is_excluded(url) and url not in found:
            found[url] = None

    return [{"url": u, "name": n} for u, n in found.items()]


def get_all_entry_urls() -> list[dict]:
    """Query all journal entries and extract unique URLs with entry backlinks."""
    dsn = settings.cross_dsn(settings.db_name, settings.db_user, settings.db_password)
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, markdown_text FROM entry
                WHERE markdown_text IS NOT NULL
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    # Deduplicate across entries, track all entry IDs per URL
    seen: dict[str, dict] = {}
    for entry_id, markdown in rows:
        for item in extract_urls(markdown):
            url = item["url"]
            if url not in seen:
                seen[url] = {"url": url, "name": item["name"], "entry_ids": [entry_id]}
            else:
                if entry_id not in seen[url]["entry_ids"]:
                    seen[url]["entry_ids"].append(entry_id)

    return list(seen.values())


def build_backlink_text(entry_ids: list[int]) -> str:
    """Build backlink text for journal entries."""
    links = [f"{JOURNAL_BASE_URL}/entry/{eid}" for eid in sorted(entry_ids)]
    if len(links) == 1:
        return f"Referenced in journal: {links[0]}"
    return "Referenced in journal:\n" + "\n".join(f"- {link}" for link in links)


def ensure_collection(client: httpx.Client, headers: dict) -> int:
    """Find or create the Journal collection, return its ID."""
    resp = client.get(f"{settings.linkwarden_url}/api/v1/collections", headers=headers)
    resp.raise_for_status()
    for coll in resp.json().get("response", resp.json()):
        if isinstance(coll, dict) and coll.get("name") == COLLECTION_NAME:
            return coll["id"]

    # Create it
    resp = client.post(
        f"{settings.linkwarden_url}/api/v1/collections",
        headers=headers,
        json={"name": COLLECTION_NAME},
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", data)["id"]


def get_existing_links(client: httpx.Client, headers: dict, collection_id: int) -> dict[str, dict]:
    """Fetch all links in the Journal collection, keyed by URL."""
    links: dict[str, dict] = {}
    cursor: int | None = None
    while True:
        params: dict = {"collectionId": collection_id}
        if cursor is not None:
            params["cursor"] = cursor
        resp = client.get(
            f"{settings.linkwarden_url}/api/v1/links",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        items = resp.json().get("response", [])
        if not isinstance(items, list) or not items:
            break
        for link in items:
            if link.get("url"):
                links[link["url"]] = link
        cursor = items[-1]["id"]
        if len(items) < 50:
            break
    return links


def update_description(client: httpx.Client, headers: dict, link: dict,
                       entry_ids: list[int], dry_run: bool) -> bool:
    """Non-destructively add backlinks to an existing link's description."""
    existing_desc = link.get("description") or ""
    backlink_text = build_backlink_text(entry_ids)

    # Check if backlinks are already present
    existing_backlinks = set(BACKLINK_PATTERN.findall(existing_desc))
    needed_backlinks = {f"journal.mees.st/entry/{eid}" for eid in entry_ids}
    if needed_backlinks.issubset(existing_backlinks):
        return False  # Already up to date

    # Remove any existing backlink section and rebuild
    lines = existing_desc.split("\n")
    cleaned = []
    for line in lines:
        if "Referenced in journal" in line or BACKLINK_PATTERN.search(line):
            continue
        cleaned.append(line)
    base_desc = "\n".join(cleaned).strip()

    if base_desc:
        new_desc = f"{base_desc}\n\n{backlink_text}"
    else:
        new_desc = backlink_text

    if dry_run:
        print(f"  [dry-run] Would update description for: {link['url']}")
        return True

    resp = client.put(
        f"{settings.linkwarden_url}/api/v1/links/{link['id']}",
        headers=headers,
        json={
            "id": link["id"],
            "name": link.get("name", ""),
            "url": link["url"],
            "description": new_desc,
            "tags": link.get("tags", []),
            "collection": {
                "id": link["collectionId"],
                "ownerId": link.get("createdById", 1),
            },
        },
    )
    if resp.status_code in (200, 201):
        return True
    print(f"  WARNING: Failed to update {link['url']}: {resp.status_code} {resp.text}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync journal URLs to Linkwarden")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without creating links")
    args = parser.parse_args()

    if not args.dry_run:
        ping_hc("/start")

    rc = 0
    try:
        if not settings.linkwarden_api_key:
            raise RuntimeError("LINKWARDEN_API_KEY not configured")

        # Extract URLs from all journal entries
        entry_urls = get_all_entry_urls()
        print(f"Journal entries: {len(entry_urls)} unique URLs extracted")

        headers = {"Authorization": f"Bearer {settings.linkwarden_api_key}"}
        with httpx.Client(timeout=30) as client:
            collection_id = ensure_collection(client, headers)
            print(f"Collection '{COLLECTION_NAME}': id={collection_id}")

            existing = get_existing_links(client, headers, collection_id)
            print(f"Already in collection: {len(existing)} URLs")

            to_create = [u for u in entry_urls if u["url"] not in existing]
            to_update = [u for u in entry_urls if u["url"] in existing]
            print(f"To create: {len(to_create)} new links")

            created = 0
            failed = 0
            updated = 0

            # Create new links with backlinks in description
            for item in to_create:
                backlink = build_backlink_text(item["entry_ids"])

                if args.dry_run:
                    name_str = f" ({item['name']})" if item["name"] else ""
                    print(f"  [dry-run] Would create: {item['url']}{name_str}")
                    created += 1
                    continue

                body: dict = {
                    "url": item["url"],
                    "collection": {"id": collection_id},
                    "description": backlink,
                }
                if item["name"]:
                    body["name"] = item["name"]

                try:
                    resp = client.post(
                        f"{settings.linkwarden_url}/api/v1/links",
                        headers=headers,
                        json=body,
                    )
                    if resp.status_code in (200, 201):
                        created += 1
                    else:
                        print(f"  WARNING: Failed to create {item['url']}: {resp.status_code} {resp.text}")
                        failed += 1
                except Exception as e:
                    print(f"  WARNING: Error creating {item['url']}: {e}")
                    failed += 1

            # Update existing links with backlinks (non-destructive)
            for item in to_update:
                link = existing[item["url"]]
                if update_description(client, headers, link, item["entry_ids"], args.dry_run):
                    updated += 1

            print(f"\nDone. Created: {created}, updated: {updated}, failed: {failed}, "
                  f"skipped (existing): {len(existing) - updated}")
            if failed:
                rc = 1

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        rc = 1

    if not args.dry_run:
        ping_hc(f"/{rc}" if rc else "")

    sys.exit(rc)


if __name__ == "__main__":
    main()
