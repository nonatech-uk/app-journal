"""Airframes.org lookup — generic fallback for countries without a dedicated register API.

Requires a login session. Credentials are passed via settings.
"""

import logging
import re

import httpx

from .base import RegisterData

log = logging.getLogger(__name__)

BASE_URL = "https://www.airframes.org"

# Module-level session cookie cache
_cookies: dict[str, str] | None = None


def _login(username: str, password: str) -> dict[str, str] | None:
    """Authenticate and return session cookies."""
    try:
        resp = httpx.post(
            f"{BASE_URL}/login",
            data={"user1": username, "passwd1": password, "submit": "Log in"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            follow_redirects=False,
        )
        cookies = {}
        for name, value in resp.cookies.items():
            cookies[name] = value
        if cookies:
            log.info("Logged in to airframes.org")
            return cookies
        log.warning("airframes.org login returned no cookies")
        return None
    except Exception:
        log.exception("Failed to log in to airframes.org")
        return None


def _get_cookies(username: str, password: str) -> dict[str, str] | None:
    global _cookies
    if _cookies is None:
        _cookies = _login(username, password)
    return _cookies


def _strip_tags(s: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", s).strip()


def _parse_result_row(html: str) -> dict | None:
    """Parse the first result row from the airframes.org search results.

    The row is a <tr> containing a link to /reg/... — we extract all <td> cells
    and map them by position to the known column order.
    """
    # Find the first data row (contains /reg/ link)
    row_match = re.search(r"<tr\s*>(<td>.*?/reg/.*?)</tr>", html, re.DOTALL)
    if not row_match:
        return None

    row_html = row_match.group(1)

    # Split into cells
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
    if len(cells) < 17:
        return None

    # Column order (from the <th> headers):
    # 0:Registration 1:Manuf 2:Model 3:Type 4:c/n 5:i/t 6:(empty) 7:ICAO24
    # 8:(empty) 9:Reg/Opr 10:built 11:test reg 12:delivery 13:prev.reg
    # 14:until 15:next reg 16:status
    result = {
        "registration": _strip_tags(cells[0]),
        "manufacturer": _strip_tags(cells[1]),
        "model": _strip_tags(cells[2]),
        "icao_type": _strip_tags(cells[3]),
        "cn": _strip_tags(cells[4]),
        "year_built": _strip_tags(cells[10]),
        "test_reg": _strip_tags(cells[11]),
        "delivery_date": _strip_tags(cells[12]),
        "status": _strip_tags(cells[16]),
    }

    # Extract operator name from cell 9 (contains link with airline name)
    opr_match = re.search(r"\[([A-Z0-9]{2})\]\s*([^<]+)", cells[9])
    if opr_match:
        result["operator"] = opr_match.group(2).strip()
    else:
        result["operator"] = _strip_tags(cells[9])

    # Extract remarks (engine info etc) — in a separate row after the data row
    remarks_match = re.search(r"Remarks:</td>\s*<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if remarks_match:
        result["remarks"] = _strip_tags(remarks_match.group(1))

    return result


def lookup(registration: str, username: str = "", password: str = "") -> RegisterData | None:
    """Look up an aircraft on airframes.org."""
    if not username or not password:
        return None

    reg = registration.upper()
    cookies = _get_cookies(username, password)
    if not cookies:
        return None

    try:
        resp = httpx.post(
            f"{BASE_URL}/",
            data={"reg1": reg, "selcal": "", "ica024": "", "submit": "submit"},
            headers={"User-Agent": "Mozilla/5.0"},
            cookies=cookies,
            timeout=15,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            log.warning("airframes.org returned %d for %s", resp.status_code, reg)
            return None

        data = _parse_result_row(resp.text)
        if not data:
            log.info("No airframes.org result for %s", reg)
            return None

        # Build engine string from remarks
        engine = None
        remarks = data.get("remarks", "")
        engine_match = re.match(r'(\d+)x\s+(.+?)\s+engines?\.?\s*$', remarks, re.IGNORECASE)
        if engine_match:
            count = engine_match.group(1)
            eng_name = engine_match.group(2)
            engine = f"{eng_name} (x{count})" if int(count) > 1 else eng_name

        year_str = data.get("year_built", "")
        year = int(year_str) if year_str.isdigit() else None

        # Deep link
        reg_slug = reg.lower().replace("-", "")
        register_url = f"{BASE_URL}/reg/{reg_slug}"

        return RegisterData(
            registration=reg,
            manufacturer=data.get("manufacturer"),
            aircraft_type=data.get("model"),
            serial_number=data.get("cn"),
            year_built=year,
            owner=data.get("operator"),
            engine=engine,
            register_url=register_url,
        )

    except Exception:
        log.exception("Failed to fetch airframes.org data for %s", registration)
        return None
