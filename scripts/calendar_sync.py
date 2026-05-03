#!/usr/bin/env python3
"""Apple Calendar -> journal.event sync.

Pulls events from selected (account, calendar_name) pairs in calendar_source
via the mac_studio MCP server, applies title-based ignore rules, expands
multi-day events into per-day rows, and upserts into the journal `event`
table. Removes-from-source detection uses soft-delete so any entry_event
links survive.

Usage:
    python scripts/calendar_sync.py                       # default Cronicle invocation
    python scripts/calendar_sync.py --since 2025-04-30    # explicit start (ISO date or datetime)
    python scripts/calendar_sync.py --until 2026-08-01
    python scripts/calendar_sync.py --days-back 365       # backfill window
    python scripts/calendar_sync.py --dry-run --no-hc

Run inside the journal container:
    podman exec journal python /app/scripts/calendar_sync.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import psycopg2

from config.settings import settings

log = logging.getLogger("calendar_sync")

SOURCE_TAG = "apple-calendar"


# ---------------------------------------------------------------------------
# MCP client
# ---------------------------------------------------------------------------

class MCPClient:
    """Minimal MCP-over-HTTP client for the local gateway.

    Streamable HTTP transport — every response is a single SSE
    `event: message` / `data: {jsonrpc...}` block, so we can parse it
    without a streaming reader.
    """

    def __init__(self, url: str, gateway_key: str = "", timeout: float = 30):
        self._url = url
        self._gateway_key = gateway_key
        self._client = httpx.Client(timeout=timeout)
        self._session_id: str | None = None
        self._headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }

    def __enter__(self) -> "MCPClient":
        self._initialize()
        if self._gateway_key:
            self.call("gateway_unlock", {"key": self._gateway_key})
        return self

    def __exit__(self, *exc) -> None:
        self._client.close()

    def _post(self, body: dict, expect_response: bool = True) -> dict | None:
        h = dict(self._headers)
        if self._session_id:
            h["mcp-session-id"] = self._session_id
        r = self._client.post(self._url, json=body, headers=h)
        r.raise_for_status()
        sid = r.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        if not expect_response:
            return None
        return self._parse_sse(r.text)

    @staticmethod
    def _parse_sse(text: str) -> dict:
        for line in text.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(text)

    def _initialize(self) -> None:
        resp = self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "journal-calendar-sync", "version": "1"},
            },
        })
        if resp.get("error"):
            raise RuntimeError(f"MCP initialize failed: {resp['error']}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_response=False)

    def call(self, name: str, arguments: dict) -> object:
        resp = self._post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        if resp.get("error"):
            raise RuntimeError(f"MCP {name} error: {resp['error']}")
        result = resp.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            msg = content[0].get("text") if content else "<no message>"
            raise RuntimeError(f"MCP {name} returned error: {msg}")
        for item in result.get("content", []):
            if item.get("type") == "text":
                txt = item.get("text", "")
                try:
                    return json.loads(txt)
                except json.JSONDecodeError:
                    return txt
        return result


# ---------------------------------------------------------------------------
# Event expansion
# ---------------------------------------------------------------------------

def _parse_iso_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def expand_event(ev: dict, tz: ZoneInfo) -> list[dict]:
    """Yield one row per local calendar day spanned by `ev`.

    For all-day events, Apple's `end` is typically 23:59:59 UTC of the last
    spanned day. We subtract one second before computing the local end-date
    to defend against clients that emit `end = 00:00:00 of next day`.
    """
    start_utc = _parse_iso_utc(ev["start"])
    end_utc = _parse_iso_utc(ev["end"])
    all_day = bool(ev.get("all_day"))

    start_local = start_utc.astimezone(tz)
    end_for_date = end_utc - timedelta(seconds=1) if all_day else end_utc
    end_local = end_for_date.astimezone(tz)

    start_d = start_local.date()
    end_d = end_local.date()
    if end_d < start_d:
        end_d = start_d

    base = {
        "external_id": ev["id"],
        "title": (ev.get("title") or "").strip() or "(untitled)",
        "notes": ev.get("notes"),
        "calendar_account": ev.get("account"),
        "calendar_name": ev.get("calendar"),
        "place_label": ev.get("location"),
    }

    span_days = (end_d - start_d).days + 1
    if span_days == 1:
        return [{
            **base,
            "event_date": start_d,
            "all_day": all_day,
            "start_time": None if all_day else start_utc,
            "end_time": None if all_day else end_utc,
        }]

    rows: list[dict] = []
    for i in range(span_days):
        day = start_d + timedelta(days=i)
        if all_day:
            rows.append({**base, "event_date": day, "all_day": True, "start_time": None, "end_time": None})
        elif i == 0:
            rows.append({**base, "event_date": day, "all_day": False, "start_time": start_utc, "end_time": None})
        elif i == span_days - 1:
            rows.append({**base, "event_date": day, "all_day": False, "start_time": None, "end_time": end_utc})
        else:
            rows.append({**base, "event_date": day, "all_day": True, "start_time": None, "end_time": None})
    return rows


# ---------------------------------------------------------------------------
# Ignore filtering
# ---------------------------------------------------------------------------

def compile_ignore_rules(rules: list[tuple[str, str]]) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for kind, value in rules:
        if kind == "regex":
            try:
                out.append(("regex", re.compile(value, re.IGNORECASE)))
            except re.error as e:
                log.warning("Skipping bad regex ignore rule %r: %s", value, e)
        elif kind == "exact":
            out.append(("exact", (value or "").strip().lower()))
        else:
            out.append(("substring", (value or "").strip().lower()))
    return out


def title_ignored(title: str, matchers: list[tuple[str, object]]) -> bool:
    t = (title or "").strip().lower()
    for kind, m in matchers:
        if kind == "regex" and m.search(title or ""):
            return True
        if kind == "exact" and t == m:
            return True
        if kind == "substring" and m and m in t:
            return True
    return False


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO event (
    external_id, event_date, title, notes, event_type_id, source,
    calendar_account, calendar_name, start_time, end_time, all_day,
    place_label, deleted_at
) VALUES (
    %(external_id)s, %(event_date)s, %(title)s, %(notes)s, %(event_type_id)s, %(source)s,
    %(calendar_account)s, %(calendar_name)s, %(start_time)s, %(end_time)s, %(all_day)s,
    %(place_label)s, NULL
)
ON CONFLICT (external_id, event_date) WHERE external_id IS NOT NULL DO UPDATE SET
    title            = EXCLUDED.title,
    notes            = EXCLUDED.notes,
    calendar_account = EXCLUDED.calendar_account,
    calendar_name    = EXCLUDED.calendar_name,
    start_time       = EXCLUDED.start_time,
    end_time         = EXCLUDED.end_time,
    all_day          = EXCLUDED.all_day,
    place_label      = EXCLUDED.place_label,
    modified_at      = now(),
    deleted_at       = NULL
"""


def get_appointment_type_id(cur) -> int:
    cur.execute("SELECT id FROM event_type WHERE name = %s", ("appointment",))
    row = cur.fetchone()
    if not row:
        raise RuntimeError("event_type 'appointment' not found — run calendar_sync_migration.sql")
    return row[0]


def soft_delete_missing(
    cur,
    account: str,
    calendar: str,
    window_start: date,
    window_end: date,
    keep_keys: set[tuple[str, date]],
) -> int:
    cur.execute(
        """
        SELECT external_id, event_date FROM event
        WHERE source = %s
          AND calendar_account = %s
          AND calendar_name = %s
          AND event_date >= %s
          AND event_date <  %s
          AND deleted_at IS NULL
        """,
        (SOURCE_TAG, account, calendar, window_start, window_end),
    )
    missing = [(eid, d) for (eid, d) in cur.fetchall() if (eid, d) not in keep_keys]
    if not missing:
        return 0
    for eid, d in missing:
        cur.execute(
            "UPDATE event SET deleted_at = now() "
            "WHERE source = %s AND external_id = %s AND event_date = %s "
            "  AND deleted_at IS NULL",
            (SOURCE_TAG, eid, d),
        )
    return len(missing)


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------

def ping_hc(suffix: str = "") -> None:
    uuid = getattr(settings, "hc_calendar_sync", "") or ""
    if not uuid:
        return
    try:
        httpx.get(f"{settings.hc_base}/{uuid}{suffix}", timeout=5)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_arg_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    if "T" in s:
        return _parse_iso_utc(s)
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Apple Calendar -> journal.event sync")
    parser.add_argument("--since", type=str, default=None, help="ISO date or datetime; default = today - days-back")
    parser.add_argument("--until", type=str, default=None, help="ISO date or datetime; default = today + days-forward")
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--days-forward", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-hc", action="store_true")
    args = parser.parse_args()

    tz = ZoneInfo(settings.calendar_local_tz)
    today_local = datetime.now(tz).date()

    until = _parse_arg_dt(args.until) or datetime.combine(
        today_local + timedelta(days=args.days_forward), datetime.min.time(), tz)
    since = _parse_arg_dt(args.since) or datetime.combine(
        today_local - timedelta(days=args.days_back), datetime.min.time(), tz)
    since_utc = since.astimezone(timezone.utc)
    until_utc = until.astimezone(timezone.utc)

    is_scheduled = not args.dry_run and not args.no_hc
    if is_scheduled:
        ping_hc("/start")

    log.info("Calendar sync window: %s -> %s (local tz %s)",
             since_utc.isoformat(), until_utc.isoformat(), tz.key)

    journal_dsn = settings.cross_dsn(settings.db_name, settings.db_user, settings.db_password)
    had_error = False

    try:
        with psycopg2.connect(journal_dsn) as conn:
            cur = conn.cursor()
            type_id = get_appointment_type_id(cur)
            cur.execute("SELECT account, calendar FROM calendar_source WHERE active ORDER BY account, calendar")
            sources = cur.fetchall()
            cur.execute("SELECT kind, value FROM calendar_ignore_rule WHERE active")
            rules = cur.fetchall()
            cur.close()

        if not sources:
            log.warning("No active calendar_source rows — nothing to sync")
            if is_scheduled:
                ping_hc("")
            return

        matchers = compile_ignore_rules(rules)
        log.info("%d active source(s); %d active ignore rule(s)", len(sources), len(matchers))

        with MCPClient(settings.mcp_gateway_url, gateway_key=settings.mcp_gateway_key) as mcp:
            for account, calendar_name in sources:
                events = mcp.call("mac_studio_calendar_get_events", {
                    "start_date": since_utc.isoformat().replace("+00:00", "Z"),
                    "end_date": until_utc.isoformat().replace("+00:00", "Z"),
                    "calendar_name": calendar_name,
                })
                if not isinstance(events, list):
                    log.warning("Unexpected MCP response for %s/%s: %r",
                                account, calendar_name, type(events).__name__)
                    continue

                # calendar_name alone collides across accounts (e.g. "Birthdays"
                # exists for two accounts). Filter on the response field.
                events = [e for e in events if e.get("account") == account]
                fetched = len(events)

                kept = [e for e in events if not title_ignored(e.get("title", ""), matchers)]
                ignored = fetched - len(kept)

                rows: list[dict] = []
                for ev in kept:
                    try:
                        rows.extend(expand_event(ev, tz))
                    except Exception as exc:
                        log.warning("Skipping event %r: %s", ev.get("id"), exc)

                for r in rows:
                    r["event_type_id"] = type_id
                    r["source"] = SOURCE_TAG

                log.info("%s/%s: fetched=%d ignored=%d expanded=%d",
                         account, calendar_name, fetched, ignored, len(rows))

                if args.dry_run:
                    continue

                with psycopg2.connect(journal_dsn) as conn:
                    cur = conn.cursor()
                    for r in rows:
                        cur.execute(UPSERT_SQL, r)
                    keep_keys = {(r["external_id"], r["event_date"]) for r in rows}
                    deleted = soft_delete_missing(
                        cur, account, calendar_name,
                        since_utc.date(), until_utc.date() + timedelta(days=1),
                        keep_keys,
                    )
                    conn.commit()
                    cur.close()
                log.info("%s/%s: upserted=%d soft_deleted=%d",
                         account, calendar_name, len(rows), deleted)

    except Exception as e:
        log.exception("Calendar sync failed: %s", e)
        had_error = True

    if is_scheduled:
        ping_hc("/fail" if had_error else "")
    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
