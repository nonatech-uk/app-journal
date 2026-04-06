"""Swiss BAZL (Federal Office of Civil Aviation) register lookup."""

import logging

import httpx

from .base import RegisterData

log = logging.getLogger(__name__)

BAZL_API = "https://app02.bazl.admin.ch/web/bazl-backend/lfr"
BAZL_WEB = "https://app02.bazl.admin.ch/web/bazl/en/#/lfr/detail"

_SEARCH_BODY_TEMPLATE = {
    "page_result_limit": 1,
    "current_page_number": 1,
    "sort_list": "registration,asc",
    "queryProperties": {
        "registration": "",
        "aircraftStatus": ["registered"],
        "aircraftModelType": "",
        "aircraftModelCat": "",
        "owner": "",
        "person": "",
        "icaoCode": "",
        "marketing": "",
        "aircraftWorksNumber": "",
        "engineModelCat": "",
        "aircraftAssignment": "",
        "ela": "",
        "elt": "",
    },
}


def lookup(registration: str) -> RegisterData | None:
    """Look up an HB- registration on the Swiss BAZL register."""
    reg = registration.upper()
    if not reg.startswith("HB-"):
        return None

    try:
        # Step 1: search to get lfrId
        body = _SEARCH_BODY_TEMPLATE.copy()
        body["queryProperties"] = {**_SEARCH_BODY_TEMPLATE["queryProperties"], "registration": reg}

        resp = httpx.post(BAZL_API, json=body, timeout=15)
        if resp.status_code != 200:
            log.warning("BAZL search returned %d for %s", resp.status_code, reg)
            return None

        results = resp.json()
        if not results:
            log.info("No BAZL results for %s", reg)
            return None

        lfr_id = results[0].get("lfrId")
        if not lfr_id:
            return None

        # Step 2: fetch full detail
        detail_resp = httpx.get(f"{BAZL_API}/{lfr_id}", timeout=15)
        if detail_resp.status_code != 200:
            log.warning("BAZL detail returned %d for %s", detail_resp.status_code, lfr_id)
            return None

        data = detail_resp.json()
        details = data.get("details", {})

        # Extract owner (Main Owner category) and operator (Main Operator)
        owner = None
        operator = None
        for oo in data.get("ownerOperators", []):
            cat_en = oo.get("holderCategory", {}).get("categoryNames", {}).get("en", "")
            if "Main Owner" in cat_en:
                owner = oo.get("ownerOperator")
            elif "Main Operator" in cat_en:
                operator = oo.get("ownerOperator")
        display_owner = operator or owner  # prefer operator for airlines

        # Engine
        engines = details.get("engines", [])
        engine = None
        if engines:
            eng = engines[0]
            name = eng.get("name", "")
            mfr = eng.get("engineManufacturer", "")
            count = int(eng.get("count", 1) or 1)
            engine = f"{mfr} {name}".strip()
            if count > 1:
                engine = f"{engine} (x{count})"

        # MTOW
        mtom = details.get("mtom")
        mtow = f"{mtom} kg" if mtom else None

        # Year
        year_str = details.get("yearOfManufacture")
        year = int(year_str) if year_str and year_str.isdigit() else None

        # Deep link
        register_url = f"{BAZL_WEB}/{reg}-{lfr_id}"

        return RegisterData(
            registration=reg,
            manufacturer=data.get("manufacturer"),
            aircraft_type=data.get("aircraftModelType"),
            serial_number=details.get("serialNumber"),
            year_built=year,
            owner=display_owner,
            mtow=mtow,
            engine=engine,
            register_url=register_url,
        )

    except Exception:
        log.exception("Failed to fetch BAZL data for %s", registration)
        return None
