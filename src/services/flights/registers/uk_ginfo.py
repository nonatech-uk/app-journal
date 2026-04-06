"""UK CAA G-INFO register lookup."""

import logging

import httpx

from .base import RegisterData

log = logging.getLogger(__name__)

GINFO_API = "https://ginfoapi.caa.co.uk/api/aircraft"
GINFO_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.caa.co.uk",
    "Referer": "https://www.caa.co.uk/aircraft-register/g-info/search-g-info/",
}
REGISTER_URL = "https://www.caa.co.uk/aircraft-register/g-info/search-g-info/"


def lookup(registration: str) -> RegisterData | None:
    """Look up a G- registration on the UK CAA G-INFO register."""
    reg = registration.upper().replace("-", "")
    if not reg.startswith("G") or len(reg) < 2:
        return None

    mark = reg[1:]  # strip the G prefix

    try:
        # Step 1: search to get AircraftID
        resp = httpx.post(
            f"{GINFO_API}/search",
            json={"registration": mark},
            headers=GINFO_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("G-INFO search returned %d for %s", resp.status_code, mark)
            return None

        results = resp.json()
        if not results:
            log.info("No G-INFO results for %s", mark)
            return None

        aircraft_id = results[0].get("AircraftID")
        if not aircraft_id:
            return None

        # Step 2: fetch full details
        detail_resp = httpx.get(
            f"{GINFO_API}/details/{aircraft_id}",
            headers=GINFO_HEADERS,
            timeout=15,
        )
        details = detail_resp.json() if detail_resp.status_code == 200 else {}

        # Step 3: fetch registration/ownership history
        history_resp = httpx.get(
            f"{GINFO_API}/registrationhistory/{aircraft_id}",
            headers=GINFO_HEADERS,
            timeout=15,
        )
        history = history_resp.json() if history_resp.status_code == 200 else {}

        # Extract fields
        reg_details = details.get("RegistrationDetails", {})
        ac = details.get("AircraftDetails", {})
        owners = details.get("RegisteredAircraftOwners", [])
        engines = ac.get("Engines", [])

        # Build ownership timeline
        timeline = []
        for entry in history.get("RegistrationHistory", []):
            owner_names = [
                o.get("RegisteredOwner", "Unknown")
                for o in entry.get("RegisteredAircraftOwners", [])
            ]
            timeline.append({
                "owner": ", ".join(owner_names),
                "from": entry.get("IssueDateRaw", "")[:10] or None,
                "to": entry.get("EndDate") or None,
                "from_display": entry.get("IssueDate", ""),
                "to_display": entry.get("EndDate") or "present",
            })

        return RegisterData(
            registration=registration.upper(),
            manufacturer=ac.get("Manufacturer"),
            aircraft_type=ac.get("Type"),
            serial_number=ac.get("SerialNumber"),
            year_built=ac.get("YearBuild"),
            owner=owners[0].get("RegisteredOwner") if owners else None,
            mtow=ac.get("Mtow"),
            engine=engines[0].get("Name") if engines else None,
            military_serial=reg_details.get("PreviousID"),
            total_hours=ac.get("TotalAirframeHours"),
            ownership_timeline=timeline,
            register_url=REGISTER_URL,
        )

    except Exception:
        log.exception("Failed to fetch G-INFO data for %s", registration)
        return None
