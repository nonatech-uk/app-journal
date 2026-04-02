"""Aircraft type lookup — OpenFlights planes database."""

import csv
import logging
from io import StringIO

import httpx

log = logging.getLogger(__name__)

PLANES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/planes.dat"

_cache = None


def load_aircraft():
    """Download and parse OpenFlights planes database. Keyed by ICAO code."""
    global _cache
    if _cache is not None:
        return _cache

    log.info("Downloading aircraft type database...")
    resp = httpx.get(PLANES_URL, timeout=30)
    resp.raise_for_status()

    aircraft = {}
    reader = csv.reader(StringIO(resp.text))
    for row in reader:
        if len(row) >= 3:
            name = row[0]
            iata = row[1] if row[1] != "\\N" else None
            icao = row[2] if row[2] != "\\N" else None
            entry = {"name": name, "iata": iata, "icao": icao}
            if icao:
                aircraft[icao] = entry
            if iata:
                aircraft[iata] = entry

    log.info("Loaded %d aircraft types", len(aircraft))
    _cache = aircraft
    return aircraft


def lookup_aircraft(code):
    """Look up aircraft by ICAO or IATA code. Returns dict with 'name' or None."""
    if not code:
        return None
    return load_aircraft().get(code)
