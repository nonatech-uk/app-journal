"""US FAA aircraft registry lookup via HTML scraping."""

import logging
import re

import httpx

from .base import RegisterData

log = logging.getLogger(__name__)

FAA_URL = "https://registry.faa.gov/aircraftinquiry/Search/NNumberResult"
REGISTER_URL = "https://registry.faa.gov/aircraftinquiry/Search/NNumberInquiry"


def _parse_data_labels(html: str) -> dict[str, str]:
    """Extract data-label field/value pairs from FAA HTML."""
    pairs = re.findall(r'data-label="([^"]+)">([^<]*)', html)
    result: dict[str, str] = {}
    for label, value in pairs:
        val = value.strip()
        if val and label:
            result[label] = val
    return result


def _parse_owner(html: str) -> str | None:
    """Extract registered owner name from the FAA HTML."""
    match = re.search(
        r'Registered Owner.*?colspan="1">Name</td>\s*<td[^>]*>([^<]+)',
        html,
        re.DOTALL,
    )
    return match.group(1).strip() if match else None


def lookup(registration: str) -> RegisterData | None:
    """Look up an N-number on the FAA registry."""
    reg = registration.upper()
    if not reg.startswith("N"):
        return None

    n_number = reg.lstrip("N")
    if not n_number:
        return None

    try:
        resp = httpx.post(
            FAA_URL,
            data={"nNumberTxt": n_number},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            log.warning("FAA registry returned %d for %s", resp.status_code, reg)
            return None

        html = resp.text
        fields = _parse_data_labels(html)
        owner = _parse_owner(html)

        if not fields.get("Serial Number") and not fields.get("Manufacturer Name"):
            log.info("No FAA data found for %s", reg)
            return None

        # Engine
        eng_mfr = fields.get("Engine Manufacturer", "").strip()
        eng_model = fields.get("Engine Model", "").strip()
        engine = f"{eng_mfr} {eng_model}".strip() or None

        # Year
        year_str = fields.get("Mfr Year", "")
        year = int(year_str) if year_str.isdigit() else None

        return RegisterData(
            registration=reg,
            manufacturer=fields.get("Manufacturer Name"),
            aircraft_type=fields.get("Model"),
            serial_number=fields.get("Serial Number"),
            year_built=year,
            owner=owner,
            engine=engine,
            register_url=REGISTER_URL,
        )

    except Exception:
        log.exception("Failed to fetch FAA data for %s", registration)
        return None
