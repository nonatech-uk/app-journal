"""Irish IAA register lookup from downloaded XLS file."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from .base import RegisterData

log = logging.getLogger(__name__)

REGISTER_URL = "https://iaa.mysrs.ie/dashboard/individual/search-aircraft-register"

# Lazy-loaded cache of the XLS data: {registration: row_dict}
_cache: dict[str, dict] | None = None


def _excel_date(serial: float) -> str:
    """Convert Excel date serial number to human-readable string."""
    try:
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=int(serial))).strftime("%-d %b %Y")
    except Exception:
        return str(serial)


def _load_register(path: str) -> dict[str, dict]:
    """Parse the IAA register XLS into a dict keyed by registration."""
    import xlrd

    wb = xlrd.open_workbook(path)
    ws = wb.sheet_by_index(0)
    data: dict[str, dict] = {}

    # Row 2 = headers, rows 3+ = data
    for i in range(3, ws.nrows):
        row = ws.row_values(i)
        reg = str(row[1]).strip()
        if not reg:
            continue
        data[reg.upper()] = {
            "registration": reg,
            "manufacturer": str(row[2]).strip() or None,
            "model": str(row[3]).strip() or None,
            "serial_number": str(row[4]).strip() or None,
            "registration_date": row[5],
            "owner": str(row[6]).strip() or None,
            "category": str(row[7]).strip() or None,
            "mtow": row[8],
            "year_built": row[9],
            "engine_manufacturer": str(row[10]).strip() or None,
            "engine_model": str(row[11]).strip().split("\n")[0] or None,
            "num_engines": row[12],
        }

    log.info("Loaded IAA register: %d aircraft", len(data))
    return data


def _get_cache(path: str) -> dict[str, dict]:
    global _cache
    if _cache is None:
        if not Path(path).exists():
            log.warning("IAA register file not found: %s", path)
            _cache = {}
        else:
            _cache = _load_register(path)
    return _cache


def lookup(registration: str, register_path: str = "/data/journal/iaa-register.xls") -> RegisterData | None:
    """Look up an EI- registration in the IAA register XLS."""
    reg = registration.upper()
    if not reg.startswith("EI-"):
        return None

    cache = _get_cache(register_path)
    entry = cache.get(reg)
    if not entry:
        log.info("Registration %s not found in IAA register", reg)
        return None

    # Build engine string
    engine_parts = []
    if entry.get("engine_manufacturer"):
        engine_parts.append(entry["engine_manufacturer"])
    if entry.get("engine_model"):
        engine_parts.append(entry["engine_model"])
    engine = " ".join(engine_parts) if engine_parts else None
    num_eng = int(entry.get("num_engines", 0) or 0)
    if engine and num_eng > 1:
        engine = f"{engine} (x{num_eng})"

    # MTOW
    mtow_val = entry.get("mtow")
    mtow = f"{int(mtow_val)} kg" if mtow_val else None

    # Year
    year_val = entry.get("year_built")
    year = int(year_val) if year_val else None

    return RegisterData(
        registration=reg,
        manufacturer=entry.get("manufacturer"),
        aircraft_type=entry.get("model"),
        serial_number=entry.get("serial_number"),
        year_built=year,
        owner=entry.get("owner"),
        mtow=mtow,
        engine=engine,
        register_url=REGISTER_URL,
    )
